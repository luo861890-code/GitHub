/**
 * 前端全局配置
 * 包含API地址、地图默认参数、主题瓦片地址、知识图谱节点颜色等
 */

export interface MapThemeConfig {
  name: string
  url: string
  attribution: string
  maxZoom: number
  subdomains: string
}

export const CONFIG = {
  apiBaseUrl: ((): string => {
    const urlParams = new URLSearchParams(window.location.search)
    const apiParam = urlParams.get('api')
    if (apiParam) {
      localStorage.setItem('carto_api_url', apiParam)
      return apiParam
    }
    const stored = localStorage.getItem('carto_api_url')
    if (stored) return stored
    return 'http://localhost:8080'
  })(),

  socketUrl: 'ws://localhost:8080/ws',

  defaultMapCenter: [30.5928, 114.3055] as [number, number],
  defaultZoom: 12,

  mapThemes: {
    standard: {
      name: '标准地图',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap 贡献者',
      maxZoom: 19,
      subdomains: 'abc',
    },
    positron: {
      name: '浅色地图',
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      attribution: '&copy; CARTO &copy; OpenStreetMap 贡献者',
      maxZoom: 20,
      subdomains: 'abcd',
    },
    dark: {
      name: '深色地图',
      url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      attribution: '&copy; CARTO &copy; OpenStreetMap 贡献者',
      maxZoom: 20,
      subdomains: 'abcd',
    },
    satellite: {
      name: '卫星地图',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: '&copy; Esri, Maxar, Earthstar Geographics',
      maxZoom: 19,
      subdomains: '',
    },
    plain: {
      name: '制图底图（无瓦片）',
      url: '',
      attribution: '',
      maxZoom: 19,
      subdomains: '',
    },
    amap_normal: {
      name: '高德地图',
      url: 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      attribution: '&copy; 高德地图',
      maxZoom: 20,
      subdomains: '1234',
    },
    amap_satellite: {
      name: '高德卫星',
      url: 'https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
      attribution: '&copy; 高德地图',
      maxZoom: 20,
      subdomains: '1234',
    },
    tianditu_vec: {
      name: '天地图矢量',
      url: 'https://t{s}.tianditu.gov.cn/DataServer?T=vec_w&x={x}&y={y}&l={z}&tk=<YOUR_TIANDITU_KEY>',
      attribution: '&copy; 天地图',
      maxZoom: 18,
      subdomains: '01234567',
    },
    tianditu_img: {
      name: '天地图影像',
      url: 'https://t{s}.tianditu.gov.cn/DataServer?T=img_w&x={x}&y={y}&l={z}&tk=<YOUR_TIANDITU_KEY>',
      attribution: '&copy; 天地图',
      maxZoom: 18,
      subdomains: '01234567',
    },
    tencent_normal: {
      name: '腾讯地图',
      url: 'https://rt{s}.map.gtimg.com/realtimerender?z={z}&x={x}&y={-y}&type=vector&style=0',
      attribution: '&copy; 腾讯地图',
      maxZoom: 20,
      subdomains: '0123',
    },
    esri_street_cn: {
      name: 'Esri中文街道',
      url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      attribution: '&copy; Esri',
      maxZoom: 19,
      subdomains: '',
    },
    hillshade: {
      name: '山体阴影（DEM）',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}',
      attribution: '&copy; Esri, USGS',
      maxZoom: 19,
      subdomains: '',
    },
    terrain: {
      name: '地形地势',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
      attribution: '&copy; Esri, USGS',
      maxZoom: 19,
      subdomains: '',
    },
  } as Record<string, MapThemeConfig>,

  kgNodeColors: {
    MapType: '#3b82f6',
    City: '#22c55e',
    Landmark: '#f97316',
    Style: '#a855f7',
    Tool: '#ec4899',
    Constraint: '#ef4444',
    Entity: '#64748b',
    CartographyRule: '#fbbf24',
    StyleRecommendation: '#06b6d4',
    MapElement: '#3b82f6',
    MapSymbol: '#a855f7',
    CartographicData: '#22c55e',
    MapProjection: '#f97316',
    InfluencingFactor: '#ef4444',
  } as Record<string, string>,

  quickCommands: [
    { label: '武汉行政图', icon: 'fa-map', message: '生成武汉市行政区划图，以省界市界县界为主，湖泊水系和主要道路为辅，标注各级行政单位，不同行政区颜色区分' },
    { label: '武汉交通图', icon: 'fa-route', message: '生成武汉市交通图，以行政边界为骨架，主要道路（高速/国道/省道/主干道）和铁路地铁为主，水系为辅，标注交通枢纽' },
    { label: '武汉地势图', icon: 'fa-mountain-sun', message: '生成武汉市地势图，叠加DEM山体阴影底图与等高线，水系和主要道路作为辅助要素' },
    { label: '武汉水系图', icon: 'fa-water', message: '生成武汉市水系图，以河流湖泊水库为主，流域界和水文站为辅，行政边界为骨架' },
    { label: '武汉旅游图', icon: 'fa-landmark', message: '生成武汉市旅游图，标注主要景点、酒店、餐饮和交通枢纽' },
    { label: '武汉基础地图', icon: 'fa-map-location-dot', message: '生成武汉市基础地图，全要素显示（道路/水系/绿地/建筑/POI）' },
    { label: '医疗资源图', icon: 'fa-hospital', message: '生成武汉市医疗资源图，显示医院、诊所、药店分布' },
    { label: '教育设施图', icon: 'fa-graduation-cap', message: '生成武汉市教育设施图，显示大学、中小学、幼儿园分布' },
    { label: '绿化覆盖图', icon: 'fa-tree', message: '生成武汉市绿化覆盖图，显示公园、绿地、森林分布' },
    { label: '商业分布图', icon: 'fa-store', message: '生成武汉市商业分布图，显示商圈、商场、超市分布' },
    { label: '美食地图', icon: 'fa-utensils', message: '生成武汉市美食图，显示餐厅、小吃街、特色美食分布' },
    { label: '知识图谱问答', icon: 'fa-diagram-project', message: '什么是专题地图？地图制图有哪些基本原则？' },
  ],

  requestTimeout: 60000,
  retryTimes: 2,
  maxMessageLength: 2000,
  kgDefaultLimit: 100,

  /** 武汉市13区柔色配色 */
  wuhanDistrictColors: [
    'match',
    ['get', 'name'],
    '江岸区', '#FFF3E0',
    '江汉区', '#E8F5E9',
    '硚口区', '#E3F2FD',
    '汉阳区', '#FCE4EC',
    '武昌区', '#F3E5F5',
    '洪山区', '#E0F7FA',
    '青山区', '#FFF8E1',
    '东西湖区', '#E8EAF6',
    '汉南区', '#F1F8E9',
    '蔡甸区', '#FFF0F5',
    '江夏区', '#EDE7F6',
    '黄陂区', '#F9FBE7',
    '新洲区', '#EFEBE9',
    '#DDEAF6',
  ] as (string | number)[],
}
