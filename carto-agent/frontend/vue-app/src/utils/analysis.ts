/**
 * 空间分析工具（浏览器端轻量实现）
 * 提供缓冲区、点面叠加（相交）、最近邻分析所需的几何计算
 */

export type LatLng = [number, number]

/** 球面距离（km，Haversine） */
export function haversineKm(a: LatLng, b: LatLng): number {
  const R = 6371
  const dLat = ((b[0] - a[0]) * Math.PI) / 180
  const dLng = ((b[1] - a[1]) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((a[0] * Math.PI) / 180) * Math.cos((b[0] * Math.PI) / 180) *
    Math.sin(dLng / 2) * Math.sin(dLng / 2)
  return 2 * R * Math.asin(Math.sqrt(s))
}

/** 点到线段距离（度空间，用于简化等） */
export function pointToSegmentDistance(p: number[], a: number[], b: number[]): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const len2 = dx * dx + dy * dy
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2
  t = Math.max(0, Math.min(1, t))
  const projX = a[0] + t * dx
  const projY = a[1] + t * dy
  return Math.sqrt((p[0] - projX) * (p[0] - projX) + (p[1] - projY) * (p[1] - projY))
}

/** 射线法判断点是否在多边形环内（点/环均为 [lat, lng]） */
export function pointInRing(point: LatLng, ring: LatLng[]): boolean {
  let inside = false
  const [lat, lng] = point
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [latI, lngI] = ring[i]
    const [latJ, lngJ] = ring[j]
    if (
      lngI > lng !== lngJ > lng &&
      lat < ((latJ - latI) * (lng - lngI)) / (lngJ - lngI) + latI
    ) {
      inside = !inside
    }
  }
  return inside
}

/** 环质心（平均） */
export function ringCentroid(ring: LatLng[]): LatLng {
  let lat = 0
  let lng = 0
  ring.forEach((p) => {
    lat += p[0]
    lng += p[1]
  })
  const n = Math.max(1, ring.length)
  return [lat / n, lng / n]
}

/** 目标点（距离/方位角） */
export function destinationPoint(center: LatLng, distanceKm: number, bearingDeg: number): LatLng {
  const [lat, lng] = center
  const dLat = distanceKm / 110.574
  const dLng = distanceKm / (111.32 * Math.cos((lat * Math.PI) / 180) || 1)
  const rad = (bearingDeg * Math.PI) / 180
  return [lat + dLat * Math.cos(rad), lng + dLng * Math.sin(rad)]
}

/** 点缓冲区：生成圆形环 */
export function bufferPoint(point: LatLng, distanceKm: number, segments = 36): LatLng[] {
  const ring: LatLng[] = []
  for (let i = 0; i < segments; i++) {
    ring.push(destinationPoint(point, distanceKm, (i * 360) / segments))
  }
  ring.push(ring[0])
  return ring
}

/** 面缓冲区（近似：从质心向外扩张每个顶点） */
export function bufferPolygon(ring: LatLng[], distanceKm: number): LatLng[] {
  if (ring.length < 3) return ring
  const centroid = ringCentroid(ring)
  const closed = ring.length > 0 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
  const pts = closed ? ring.slice(0, -1) : [...ring]
  const result: LatLng[] = pts.map((p) => {
    const d = haversineKm(centroid, p)
    const factor = d > 0.0001 ? (d + distanceKm) / d : 1 + distanceKm / 0.1
    return [
      centroid[0] + (p[0] - centroid[0]) * factor,
      centroid[1] + (p[1] - centroid[1]) * factor,
    ]
  })
  result.push(result[0])
  return result
}

/** 对图层坐标执行缓冲区：points -> 圆形环；polygons -> 扩张环 */
export function bufferCoordinates(
  coords: any,
  type: string,
  distanceKm: number
): LatLng[][] {
  const rings: LatLng[][] = []
  if (type === 'polygon' || type === 'area') {
    ;(coords || []).forEach((ring: any) => {
      if (Array.isArray(ring) && Array.isArray(ring[0])) {
        rings.push(bufferPolygon(ring as LatLng[], distanceKm))
      }
    })
  } else {
    ;(coords || []).forEach((p: any) => {
      if (Array.isArray(p) && p.length >= 2) {
        rings.push(bufferPoint([p[0], p[1]], distanceKm))
      }
    })
  }
  return rings
}

/** 点面叠加：保留落在目标多边形内的点 */
export function intersectPointPolygon(points: LatLng[], polygons: LatLng[][]): LatLng[] {
  return points.filter((p) => polygons.some((ring) => pointInRing(p, ring)))
}

/** 最近邻：返回每个源点到最近目标点的连线与距离 */
export function nearestPairs(
  sources: LatLng[],
  targets: LatLng[]
): { segment: LatLng[]; distanceKm: number }[] {
  return sources.map((s) => {
    let best: LatLng = targets[0] || s
    let bestD = targets.length ? Infinity : 0
    targets.forEach((t) => {
      const d = haversineKm(s, t)
      if (d < bestD) {
        bestD = d
        best = t
      }
    })
    return { segment: [s, best], distanceKm: bestD }
  })
}

/** 提取图层的坐标点集（所有要素） */
export function layerPoints(coords: any, type: string): LatLng[] {
  const pts: LatLng[] = []
  ;(coords || []).forEach((c: any) => {
    if (Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number') {
      pts.push([c[0], c[1]])
    } else if (Array.isArray(c) && Array.isArray(c[0])) {
      c.forEach((p: any) => {
        if (Array.isArray(p) && p.length >= 2) pts.push([p[0], p[1]])
      })
    }
  })
  return pts
}

/** 提取图层的多边形环集 */
export function layerRings(coords: any, type: string): LatLng[][] {
  const rings: LatLng[][] = []
  if (type !== 'polygon' && type !== 'area') return rings
  ;(coords || []).forEach((ring: any) => {
    if (Array.isArray(ring) && Array.isArray(ring[0])) {
      rings.push(ring as LatLng[])
    }
  })
  return rings
}

// ========== 矢量叠加工具（裁剪 / 相交 / 并集） ==========

/** 判断是否为有效的 [lat, lng] 坐标对 */
function isValidLatLng(c: any): c is LatLng {
  return (
    Array.isArray(c) &&
    c.length >= 2 &&
    typeof c[0] === 'number' &&
    typeof c[1] === 'number' &&
    isFinite(c[0]) &&
    isFinite(c[1])
  )
}

/** 坐标嵌套深度：[lat,lng]=1，[[lat,lng],...]=2，[[[lat,lng],...],...]=3 */
function coordsDepth(c: any): number {
  let depth = 0
  let cur = c
  while (Array.isArray(cur)) {
    depth++
    cur = cur[0]
  }
  return depth
}

/** 线段交点（平面近似），参数化求交，返回 [lat, lng] 或 null */
export function segmentIntersection(a: LatLng, b: LatLng, c: LatLng, d: LatLng): LatLng | null {
  const s1x = b[0] - a[0]
  const s1y = b[1] - a[1]
  const s2x = d[0] - c[0]
  const s2y = d[1] - c[1]
  const denom = -s2x * s1y + s1x * s2y
  if (Math.abs(denom) < 1e-12) return null
  const s = (-s1y * (a[0] - c[0]) + s1x * (a[1] - c[1])) / denom
  const t = (s2x * (a[1] - c[1]) - s2y * (a[0] - c[0])) / denom
  if (s >= 0 && s <= 1 && t >= 0 && t <= 1) {
    return [a[0] + t * s1x, a[1] + t * s1y]
  }
  return null
}

function distSq(a: LatLng, b: LatLng): number {
  const dlat = a[0] - b[0]
  const dlng = a[1] - b[1]
  return dlat * dlat + dlng * dlng
}

/** 线段 a-b 与环所有边的交点（未排序去重） */
function ringIntersections(a: LatLng, b: LatLng, ring: LatLng[]): LatLng[] {
  const pts: LatLng[] = []
  const closed = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
  const n = closed ? ring.length - 1 : ring.length
  for (let i = 0; i < n; i++) {
    const c = ring[i]
    const d = ring[(i + 1) % n]
    const inter = segmentIntersection(a, b, c, d)
    if (inter) pts.push(inter)
  }
  return pts
}

/** 线要素裁剪到多边形内：返回落在环内的子线段集合 */
export function clipPolylineToRing(polyline: LatLng[], ring: LatLng[]): LatLng[][] {
  const result: LatLng[][] = []
  if (polyline.length < 2) return result
  let current: LatLng[] = []
  for (let i = 0; i < polyline.length - 1; i++) {
    const a = polyline[i]
    const b = polyline[i + 1]
    const aIn = pointInRing(a, ring)
    const bIn = pointInRing(b, ring)
    if (aIn) {
      if (current.length === 0) current.push(a)
      if (bIn) {
        current.push(b)
      } else {
        const inters = ringIntersections(a, b, ring)
        if (inters.length > 0) {
          inters.sort((p, q) => distSq(a, p) - distSq(a, q))
          current.push(inters[0])
          result.push(current)
          current = []
        }
      }
    } else if (bIn) {
      const inters = ringIntersections(a, b, ring)
      if (inters.length > 0) {
        inters.sort((p, q) => distSq(a, p) - distSq(a, q))
        current = [inters[0], b]
      }
    } else {
      const inters = ringIntersections(a, b, ring)
      if (inters.length >= 2) {
        inters.sort((p, q) => distSq(a, p) - distSq(a, q))
        result.push([inters[0], inters[inters.length - 1]])
      }
    }
  }
  if (current.length > 0) result.push(current)
  return result
}

/** 环闭合（去重首尾重复点） */
function closedRing(ring: LatLng[]): LatLng[] {
  if (ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]) {
    return ring
  }
  return [...ring, ring[0]]
}

/** 按围绕质心的极角排序点集（用于构造交集面） */
function sortByAngleAroundCentroid(pts: LatLng[]): LatLng[] {
  const c = ringCentroid(pts)
  return pts
    .slice()
    .sort((a, b) => {
      return Math.atan2(a[0] - c[0], a[1] - c[1]) - Math.atan2(b[0] - c[0], b[1] - c[1])
    })
}

/** 面∩面：顶点收集 + 极角排序（凸面精确，凹面为轻量近似） */
export function intersectRings(subject: LatLng[], clip: LatLng[]): LatLng[] {
  const subj = closedRing(subject)
  const clipR = closedRing(clip)
  const pts: LatLng[] = []

  // subject 顶点落在 clip 内
  subj.forEach((p) => { if (pointInRing(p, clipR)) pts.push([p[0], p[1]]) })
  // clip 顶点落在 subject 内
  clipR.forEach((p) => { if (pointInRing(p, subj)) pts.push([p[0], p[1]]) })
  // 两环边界的交点
  for (let i = 0; i < subj.length - 1; i++) {
    for (let j = 0; j < clipR.length - 1; j++) {
      const inter = segmentIntersection(subj[i], subj[i + 1], clipR[j], clipR[j + 1])
      if (inter) pts.push(inter)
    }
  }

  // 去重
  const dedup: LatLng[] = []
  pts.forEach((p) => {
    if (!dedup.some((q) => distSq(p, q) < 1e-12)) dedup.push(p)
  })
  if (dedup.length < 3) return []
  return sortByAngleAroundCentroid(dedup)
}

// ========== 图层几何提取（兼容 coordinates 与 features 两种存储） ==========

export interface LayerGeometries {
  points: LatLng[]
  lines: LatLng[][]
  rings: LatLng[][]
}

function geomKind(type: string): 'point' | 'line' | 'area' {
  const t = (type || '').toLowerCase()
  if (['point', 'circlemarker', 'marker', 'textlabel', 'label'].includes(t)) return 'point'
  if (['polygon', 'area'].includes(t)) return 'area'
  if (['polyline', 'line', 'linestring'].includes(t)) return 'line'
  return 'point'
}

/** 从完整图层数据提取点/线/面几何（兼容 features 型与 coordinates 型） */
export function extractLayerGeometries(layer: any): LayerGeometries {
  const geo: LayerGeometries = { points: [], lines: [], rings: [] }
  const collect = (c: any, featType?: string) => {
    if (!Array.isArray(c)) return
    const kind = geomKind(featType || layer?.type || '')
    const depth = coordsDepth(c)
    if (depth === 1) {
      if (isValidLatLng(c)) geo.points.push([c[0], c[1]])
    } else if (depth === 2) {
      const pts = c.filter(isValidLatLng) as LatLng[]
      if (pts.length === 0) return
      if (kind === 'area') {
        if (pts.length >= 3) geo.rings.push(pts)
      } else if (kind === 'line') {
        if (pts.length >= 2) geo.lines.push(pts)
      } else {
        pts.forEach((p) => geo.points.push(p))
      }
    } else {
      // depth >= 3：多环 / 多线，逐个子结构递归
      c.forEach((sub: any) => collect(sub, featType || layer?.type))
    }
  }

  if (Array.isArray(layer?.features) && layer.features.length > 0) {
    layer.features.forEach((f: any) => collect(f?.coordinates, f?.type))
  } else if (layer?.coordinates) {
    collect(layer.coordinates)
  }
  return geo
}

// ========== 投影转换（WGS84 经纬度 <-> Web Mercator 米制） ==========

const WGS84_SEMI_MAJOR = 6378137
const MAX_MERCATOR = 20037508.342789244

/** 经纬度（EPSG:4326）→ Web Mercator（EPSG:3857）米制坐标 [x, y] */
export function lonLatToWebMercator(ll: LatLng): [number, number] {
  const [lat, lng] = ll
  const x = (lng * MAX_MERCATOR) / 180
  const latClamped = Math.max(-85.05112878, Math.min(85.05112878, lat))
  const y = Math.log(Math.tan(((90 + latClamped) * Math.PI) / 360)) * WGS84_SEMI_MAJOR
  return [x, y]
}

/** Web Mercator（EPSG:3857）米制坐标 [x, y] → 经纬度（EPSG:4326） */
export function webMercatorToLonLat(xy: [number, number]): LatLng {
  const [x, y] = xy
  const lng = (x * 180) / MAX_MERCATOR
  const lat = (2 * Math.atan(Math.exp(y / WGS84_SEMI_MAJOR)) - Math.PI / 2) * (180 / Math.PI)
  return [lat, lng]
}

/** 递归转换坐标（自动识别 [lat,lng] 叶节点并应用转换函数） */
export function projectCoordsDeep(
  coords: any,
  fn: (ll: LatLng) => [number, number]
): any {
  if (!Array.isArray(coords)) return coords
  if (isValidLatLng(coords)) return fn([coords[0], coords[1]])
  return coords.map((c: any) => projectCoordsDeep(c, fn))
}
