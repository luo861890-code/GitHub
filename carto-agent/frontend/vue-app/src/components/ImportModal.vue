<template>
  <Teleport to="body">
    <div class="import-overlay" @click.self="appStore.toggleImportModal()">
      <div class="import-dialog">
        <div class="import-header">
          <span><i class="fa-solid fa-file-import"></i> 数据导入</span>
          <button class="import-close" @click="appStore.toggleImportModal()">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="import-tabs">
          <button class="import-tab" :class="{ active: importMode === 'doc' }" @click="importMode = 'doc'">
            <i class="fa-solid fa-file-lines"></i> 文档 → 知识图谱
          </button>
          <button class="import-tab" :class="{ active: importMode === 'geo' }" @click="importMode = 'geo'">
            <i class="fa-solid fa-map"></i> GeoJSON/SHP → 地图图层
          </button>
          <button class="import-tab" :class="{ active: importMode === 'raster' }" @click="importMode = 'raster'">
            <i class="fa-solid fa-image"></i> 栅格/影像
          </button>
        </div>
        <div class="import-body">
          <template v-if="importMode === 'doc'">
            <div class="import-hint">
              <i class="fa-solid fa-circle-info"></i>
              <span>粘贴文档内容，系统将自动抽取实体与关系并添加到知识图谱中。</span>
            </div>
            <div class="import-field">
              <label>文档内容</label>
              <textarea
                v-model="content"
                class="import-textarea"
                placeholder="在此粘贴文档内容..."
                rows="10"
              ></textarea>
            </div>
            <div class="import-field">
              <label>实体标签（可选，逗号分隔）</label>
              <input v-model="labels" type="text" class="import-input" placeholder="如 City, Landmark, MapType" />
            </div>
            <div v-if="result" class="import-result" :class="{ error: result.error }">
              <template v-if="!result.error">
                <div class="import-result-title">
                  <i class="fa-solid fa-circle-check"></i> 导入成功
                </div>
                <div class="import-stats">
                  <div class="import-stat">
                    <span class="import-stat-num">{{ result.entities || 0 }}</span>
                    <span class="import-stat-label">实体</span>
                  </div>
                  <div class="import-stat">
                    <span class="import-stat-num">{{ result.relations || 0 }}</span>
                    <span class="import-stat-label">关系</span>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="import-result-title error">
                  <i class="fa-solid fa-circle-xmark"></i> 导入失败
                </div>
                <div class="import-error-msg">{{ result.error }}</div>
              </template>
            </div>
          </template>

          <template v-else-if="importMode === 'raster'">
            <div class="import-hint">
              <i class="fa-solid fa-circle-info"></i>
              <span>导入栅格数据（GeoTIFF/PNG/JPG）作为底图或分析图层。支持DEM高程数据生成山体阴影。</span>
            </div>
            <div class="import-field">
              <label>栅格文件</label>
              <input type="file" accept=".tif,.tiff,.png,.jpg,.jpeg,.img" class="import-input" @change="onRasterFile" />
            </div>
            <div class="import-field">
              <label>图层名称</label>
              <input v-model="rasterName" type="text" class="import-input" placeholder="如：DEM高程数据" />
            </div>
            <div class="import-field">
              <label>渲染方式</label>
              <select v-model="rasterRender" class="import-input">
                <option value="hillshade">山体阴影（Hillshade）</option>
                <option value="stretch">灰度拉伸</option>
                <option value="pseudo">伪彩色</option>
                <option value="overlay">底图叠加</option>
              </select>
            </div>
            <div v-if="rasterResult" class="import-result" :class="{ error: rasterResult.error }">
              <template v-if="!rasterResult.error">
                <div class="import-result-title">
                  <i class="fa-solid fa-circle-check"></i> 栅格已导入
                </div>
                <div class="import-stats">
                  <div class="import-stat">
                    <span class="import-stat-num">{{ rasterResult.size }}</span>
                    <span class="import-stat-label">文件大小</span>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="import-result-title error">
                  <i class="fa-solid fa-circle-xmark"></i> 导入失败
                </div>
                <div class="import-error-msg">{{ rasterResult.error }}</div>
              </template>
            </div>
          </template>

          <template v-else>
            <div class="import-hint">
              <i class="fa-solid fa-circle-info"></i>
              <span>选择本地 GeoJSON/SHP 文件（点/线/面），导入为当前地图的新图层。SHP文件需同时上传.shp和.dbf。</span>
            </div>
            <div class="import-field">
              <label>地理数据文件</label>
              <input type="file" accept=".geojson,.json,.shp,.dbf,.shx,.prj,application/geo+json" class="import-input" @change="onGeoFile" />
            </div>
            <div class="import-field">
              <label>图层名称</label>
              <input v-model="geoName" type="text" class="import-input" placeholder="如：自定义水系" />
            </div>
            <div class="import-field">
              <label>要素类型</label>
              <select v-model="geoType" class="import-input">
                <option value="auto">自动识别</option>
                <option value="point">点要素</option>
                <option value="line">线要素</option>
                <option value="polygon">面要素</option>
              </select>
            </div>
            <div v-if="geoResult" class="import-result" :class="{ error: geoResult.error }">
              <template v-if="!geoResult.error">
                <div class="import-result-title">
                  <i class="fa-solid fa-circle-check"></i> 图层已导入
                </div>
                <div class="import-stats">
                  <div class="import-stat">
                    <span class="import-stat-num">{{ geoResult.count }}</span>
                    <span class="import-stat-label">要素</span>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="import-result-title error">
                  <i class="fa-solid fa-circle-xmark"></i> 导入失败
                </div>
                <div class="import-error-msg">{{ geoResult.error }}</div>
              </template>
            </div>
          </template>
        </div>
        <div class="import-footer">
          <button class="btn secondary" @click="appStore.toggleImportModal()">取消</button>
          <button v-if="importMode === 'doc'" class="btn primary" :disabled="importing" @click="submit">
            <div v-if="importing" class="btn-spinner"></div>
            <i v-else class="fa-solid fa-upload"></i> 导入文档
          </button>
          <button v-else-if="importMode === 'raster'" class="btn primary" :disabled="rasterImporting || !mapStore.currentMapId" @click="submitRaster">
            <div v-if="rasterImporting" class="btn-spinner"></div>
            <i v-else class="fa-solid fa-upload"></i> 导入栅格
          </button>
          <button v-else class="btn primary" :disabled="geoImporting || !mapStore.currentMapId" @click="submitGeo">
            <div v-if="geoImporting" class="btn-spinner"></div>
            <i v-else class="fa-solid fa-upload"></i> 导入图层
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/appStore'
import { useKGStore } from '@/stores/kgStore'
import { useMapStore } from '@/stores/mapStore'
import api from '@/services/api'

const appStore = useAppStore()
const kgStore = useKGStore()
const mapStore = useMapStore()

const importMode = ref<'doc' | 'geo' | 'raster'>('doc')
const content = ref('')
const labels = ref('')
const importing = ref(false)
const result = ref<{ entities?: number; relations?: number; error?: string } | null>(null)
const geoFile = ref<File | null>(null)
const geoName = ref('')
const geoType = ref('auto')
const geoImporting = ref(false)
const geoResult = ref<{ count?: number; error?: string } | null>(null)
const rasterFile = ref<File | null>(null)
const rasterName = ref('')
const rasterRender = ref('hillshade')
const rasterImporting = ref(false)
const rasterResult = ref<{ size?: string; error?: string } | null>(null)

async function submit() {
  const text = content.value.trim()
  if (!text) {
    alert('请输入文档内容')
    return
  }
  const entityLabels = labels.value
    ? labels.value.split(',').map((s) => s.trim()).filter(Boolean)
    : null

  importing.value = true
  result.value = null
  try {
    const resp = await api.importDocument(text, entityLabels)
    const data = resp.data || resp
    result.value = {
      entities: data?.entities?.length ?? 0,
      relations: data?.relations?.length ?? 0,
    }
    await kgStore.loadGraph()
    setTimeout(() => appStore.toggleImportModal(), 2000)
  } catch (e: any) {
    result.value = { error: e.message || '导入失败' }
  } finally {
    importing.value = false
  }
}

function onGeoFile(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  if (!files.length) {
    geoFile.value = null
    return
  }
  // 多文件（SHP 场景：.shp/.dbf/.shx/.prj）→ 前端打包为 zip 上传；单文件直接传
  if (files.length > 1) {
    void packShpZip(files)
  } else {
    geoFile.value = files[0]
  }
}

/** 浏览器端极简 zip 打包（store 无压缩），用于 SHP 多文件场景 */
function crc32(data: Uint8Array): number {
  let crc = 0xffffffff
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i]
    for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1))
  }
  return (crc ^ 0xffffffff) >>> 0
}

async function packShpZip(files: File[]) {
  try {
    const items: { name: string; data: Uint8Array }[] = []
    for (const f of files) {
      items.push({ name: f.name, data: new Uint8Array(await f.arrayBuffer()) })
    }
    const enc = new TextEncoder()
    const parts: BlobPart[] = []
    const central: BlobPart[] = []
    let offset = 0
    for (const it of items) {
      const nameBytes = enc.encode(it.name)
      const crc = crc32(it.data)
      const size = it.data.length
      const lfh = new DataView(new ArrayBuffer(30))
      lfh.setUint32(0, 0x04034b50, true)
      lfh.setUint16(4, 20, true)
      lfh.setUint32(14, crc, true)
      lfh.setUint32(18, size, true)
      lfh.setUint32(22, size, true)
      lfh.setUint16(26, nameBytes.length, true)
      parts.push(lfh.buffer, nameBytes, it.data)
      const cdh = new DataView(new ArrayBuffer(46))
      cdh.setUint32(0, 0x02014b50, true)
      cdh.setUint16(4, 20, true)
      cdh.setUint16(6, 20, true)
      cdh.setUint32(16, crc, true)
      cdh.setUint32(20, size, true)
      cdh.setUint32(24, size, true)
      cdh.setUint16(28, nameBytes.length, true)
      cdh.setUint32(42, offset, true)
      central.push(cdh.buffer, nameBytes)
      offset += 30 + nameBytes.length + size
    }
    const eocd = new DataView(new ArrayBuffer(22))
    eocd.setUint32(0, 0x06054b50, true)
    eocd.setUint16(8, items.length, true)
    eocd.setUint16(10, items.length, true)
    let centralSize = 0
    for (const c of central) centralSize += (c as ArrayBuffer).byteLength
    eocd.setUint32(12, centralSize, true)
    eocd.setUint32(16, offset, true)
    parts.push(...central, eocd.buffer)
    const zipBlob = new Blob(parts, { type: 'application/zip' })
    const shpName = files.find((f) => /\.shp$/i.test(f.name))?.name || files[0].name
    geoFile.value = new File([zipBlob], shpName.replace(/\.shp$/i, '') + '_shp.zip', { type: 'application/zip' })
  } catch (err: any) {
    alert('SHP 文件打包失败: ' + (err.message || err))
    geoFile.value = null
  }
}

function onRasterFile(e: Event) {
  const input = e.target as HTMLInputElement
  rasterFile.value = input.files?.[0] || null
}

async function submitRaster() {
  if (!rasterFile.value) {
    alert('请选择栅格文件')
    return
  }
  const mapId = mapStore.currentMapId
  if (!mapId) {
    alert('当前没有地图，请先生成地图')
    return
  }
  const name = rasterName.value.trim() || rasterFile.value.name
  rasterImporting.value = true
  rasterResult.value = null
  try {
    // 栅格图层作为imageOverlay添加到地图
    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string
      const rasterLayer: any = {
        id: 'raster_' + Date.now(),
        type: 'imageOverlay',
        name: name,
        imageUrl: dataUrl,
        renderMode: rasterRender.value,
        style: { opacity: 0.8 },
      }
      // 添加到mapStore
      const maxOrder = Math.max(0, ...mapStore.sortedLayers.map((l: any) => l.order))
      mapStore.layerGroups[rasterLayer.id] = { visible: true, data: rasterLayer, order: maxOrder + 1 }
      rasterResult.value = { size: (rasterFile.value!.size / 1024).toFixed(1) + ' KB' }
      const el = document.getElementById('map-container')
      el?.dispatchEvent(new CustomEvent('map-refresh-layers'))
      setTimeout(() => appStore.toggleImportModal(), 1800)
    }
    reader.readAsDataURL(rasterFile.value)
  } catch (e: any) {
    rasterResult.value = { error: e.message || '导入失败' }
  } finally {
    rasterImporting.value = false
  }
}

async function submitGeo() {
  if (!geoFile.value) {
    alert('请选择地理数据文件（GeoJSON / SHP）')
    return
  }
  const mapId = mapStore.currentMapId
  if (!mapId) {
    alert('当前没有地图，请先生成地图')
    return
  }
  const name = geoName.value.trim() || geoFile.value.name.replace(/\.(geojson|json|zip|shp)$/i, '')
  geoImporting.value = true
  geoResult.value = null
  try {
    const resp = await api.importGeoJSON(mapId, geoFile.value, name, geoType.value)
    const data = resp.data || resp
    const last = (data.layers || []).slice(-1)[0]
    geoResult.value = {
      count: last ? (last.coordinates || []).length : 0,
    }
    const refreshed = await api.getMap(mapId)
    mapStore.setMapData(refreshed.data || refreshed)
    const el = document.getElementById('map-container')
    el?.dispatchEvent(new CustomEvent('map-refresh-layers'))
    setTimeout(() => appStore.toggleImportModal(), 1800)
  } catch (e: any) {
    geoResult.value = { error: e.message || '导入失败' }
  } finally {
    geoImporting.value = false
  }
}
</script>

<style scoped>
.import-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.import-dialog {
  width: 560px;
  max-height: 85vh;
  background: #fff;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.import-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px 18px;
  border-bottom: 1px solid var(--color-border);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary);
}

.import-tabs {
  display: flex;
  gap: 6px;
  padding: 10px 18px 0;
}

.import-tab {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 8px 8px 0 0;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-bottom: none;
}

.import-tab.active {
  color: var(--color-primary);
  border-color: var(--color-primary-light);
  background: rgba(124, 58, 237, 0.05);
  font-weight: 600;
}

.import-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  border-radius: 50%;
  cursor: pointer;
}

.import-close:hover {
  background: var(--color-bg);
}

.import-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

.import-hint {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 14px;
}

.import-field {
  margin-bottom: 14px;
}

.import-field label {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

.import-textarea,
.import-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
  resize: vertical;
}

.import-textarea:focus,
.import-input:focus {
  border-color: var(--color-primary-light);
}

.import-result {
  padding: 12px;
  background: #f0fdf4;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 8px;
}

.import-result.error {
  background: #fef2f2;
  border-color: rgba(239, 68, 68, 0.3);
}

.import-result-title {
  color: #15803d;
  font-weight: 600;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.import-result-title.error {
  color: #b91c1c;
}

.import-stats {
  display: flex;
  gap: 20px;
  margin-top: 10px;
}

.import-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.import-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: #15803d;
}

.import-stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.import-error-msg {
  margin-top: 6px;
  font-size: 12px;
  color: #b91c1c;
}

.import-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 18px;
  border-top: 1px solid var(--color-border);
  background: #fafbfc;
}

.btn {
  padding: 8px 18px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn.secondary {
  background: #f1f5f9;
  color: var(--color-text);
}

.btn.primary {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
