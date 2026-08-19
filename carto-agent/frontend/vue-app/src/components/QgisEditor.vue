<template>
  <div class="qgis-editor">
    <!-- 菜单栏 -->
    <div class="qgis-menu-bar">
      <div class="menu-item" v-for="menu in menus" :key="menu.id">
        <span class="menu-label">{{ menu.label }}</span>
        <div class="menu-dropdown" v-if="menu.items">
          <template v-for="item in menu.items" :key="item.id">
            <div v-if="item.type === 'separator'" class="menu-separator"></div>
            <div v-else class="menu-item-child" @click="handleMenuAction(item)">
              <i :class="item.icon" v-if="item.icon"></i>
              <span>{{ item.label }}</span>
              <span class="shortcut" v-if="item.shortcut">{{ item.shortcut }}</span>
            </div>
          </template>
        </div>
      </div>
      <div class="menu-bar-right">
        <button class="back-btn" @click="goBack">
          <i class="fa-solid fa-arrow-left"></i>
          <span>返回主界面</span>
        </button>
      </div>
    </div>

    <!-- 工具栏 - 动态渲染工具组 -->
    <div class="qgis-toolbar">
      <div 
        class="toolbar-group" 
        v-for="group in activeToolGroups" 
        :key="group.id"
      >
        <span class="toolbar-label">{{ group.label }}</span>
        <div class="toolbar-separator"></div>
        <button 
          class="tool-btn" 
          v-for="tool in group.tools" 
          :key="tool.id"
          :title="tool.title"
          :class="{ active: activeTool === tool.id }"
          @click="handleToolClick(tool)"
        >
          <i :class="tool.icon"></i>
        </button>
      </div>
      
      <!-- 工具组自定义按钮 -->
      <div class="toolbar-group toolbar-customize">
        <div class="toolbar-separator"></div>
        <button 
          class="tool-btn tool-customize-btn" 
          title="自定义工具栏"
          @click="showToolGroupSelector = !showToolGroupSelector"
        >
          <i class="fa-solid fa-sliders"></i>
        </button>
        
        <!-- 工具组选择器下拉菜单 -->
        <div class="tool-group-selector" v-if="showToolGroupSelector">
          <div class="selector-header">
            <i class="fa-solid fa-toolbox"></i>
            <span>工具栏工具组</span>
          </div>
          <div class="selector-hint">勾选要显示的工具组</div>
          <div class="selector-list">
            <div 
              class="selector-item" 
              v-for="group in allToolGroups" 
              :key="group.id"
              @click="toggleToolGroup(group.id)"
            >
              <i 
                :class="activeToolGroupIds.includes(group.id) ? 'fa-solid fa-square-check' : 'fa-regular fa-square'"
              ></i>
              <span>{{ group.label }}</span>
              <span class="tool-count">{{ group.tools.length }}个工具</span>
            </div>
          </div>
          <div class="selector-footer">
            <button class="selector-btn" @click="activeToolGroupIds = allToolGroups.map(g => g.id)">全选</button>
            <button class="selector-btn" @click="activeToolGroupIds = []">清空</button>
            <button class="selector-btn primary" @click="showToolGroupSelector = false">完成</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 主体区域 -->
    <div class="qgis-main">
      <!-- 左侧面板 -->
      <div class="qgis-left-panel">
        <div class="panel-tabs">
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'layers' }"
            @click="leftPanelTab = 'layers'"
          >
            <i class="fa-solid fa-layer-group"></i>
            <span>图层</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'style' }"
            @click="leftPanelTab = 'style'"
          >
            <i class="fa-solid fa-palette"></i>
            <span>样式</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: leftPanelTab === 'history' }"
            @click="leftPanelTab = 'history'"
          >
            <i class="fa-solid fa-clock-rotate-left"></i>
            <span>历史</span>
          </button>
        </div>

        <div class="panel-content">
          <!-- 图层面板 -->
          <div v-show="leftPanelTab === 'layers'" class="layers-panel">
            <div class="panel-toolbar">
              <button class="panel-tool-btn" title="添加图层" @click="addLayerByDialog">
                <i class="fa-solid fa-plus"></i>
              </button>
              <button class="panel-tool-btn" title="移除图层" @click="removeSelectedLayer">
                <i class="fa-solid fa-minus"></i>
              </button>
              <button class="panel-tool-btn" title="上移图层" @click="moveLayer(-1)">
                <i class="fa-solid fa-arrow-up"></i>
              </button>
              <button class="panel-tool-btn" title="下移图层" @click="moveLayer(1)">
                <i class="fa-solid fa-arrow-down"></i>
              </button>
              <div class="panel-tool-separator"></div>
              <button class="panel-tool-btn" title="打开属性表" @click="openAttrTable">
                <i class="fa-solid fa-table"></i>
              </button>
              <button class="panel-tool-btn" title="缩放到图层" @click="zoomToSelectedLayer">
                <i class="fa-solid fa-magnifying-glass"></i>
              </button>
            </div>

            <div class="layer-tree">
              <div v-if="mapStore.sortedLayers.length === 0" class="layer-empty">暂无图层</div>
              <template v-for="(group, gi) in groupedLayerTree" :key="gi">
                <div v-if="group.name" class="layer-group-header">
                  <i class="fa-solid fa-folder group-icon"></i>
                  {{ group.name }}
                  <span class="group-count">{{ group.layers.length }}</span>
                </div>
                <div
                  v-for="layer in group.layers"
                  :key="layer.id"
                  class="layer-item"
                  :class="{ selected: selectedLayer === layer.id }"
                  @click="selectedLayer = layer.id"
                >
                  <input
                    type="checkbox"
                    :checked="layer.visible"
                    @change="mapStore.toggleLayer(layer.id, ($event.target as HTMLInputElement).checked)"
                    @click.stop
                  />
                  <span class="layer-icon" :class="layerIconClass(layer.data.type)"></span>
                  <span class="layer-name-text">{{ layer.data.name }}</span>
                </div>
              </template>
            </div>
          </div>

          <!-- 样式面板 -->
          <div v-show="leftPanelTab === 'style'" class="style-panel">
            <div class="style-header">
              <span>图层样式</span>
              <span class="layer-name">{{ selectedLayerName }}</span>
            </div>
            <div class="style-content">
              <div class="style-section">
                <label>渲染方式</label>
                <select class="style-select" v-model="renderMode">
                  <option>单点渲染</option>
                </select>
              </div>
              <div class="style-section">
                <label>填充颜色（面）</label>
                <div class="color-row">
                  <input type="color" :value="styleFill" @input="updateStyle('fillColor', ($event.target as HTMLInputElement).value)" class="color-input" />
                  <span class="color-hex">{{ styleFill }}</span>
                </div>
              </div>
              <div class="style-section">
                <label>颜色（线/边框/点）</label>
                <div class="color-row">
                  <input type="color" :value="styleColor" @input="updateStyle('color', ($event.target as HTMLInputElement).value)" class="color-input" />
                  <span class="color-hex">{{ styleColor }}</span>
                </div>
              </div>
              <div class="style-section">
                <label>线宽</label>
                <input type="range" min="0" max="10" :value="styleWeight" @input="updateStyle('weight', parseInt(($event.target as HTMLInputElement).value))" class="style-slider" />
                <span class="slider-value">{{ styleWeight }}px</span>
              </div>
              <div class="style-section">
                <label>透明度</label>
                <input type="range" min="0" max="100" :value="styleOpacity * 100" @input="updateStyle('opacity', parseInt(($event.target as HTMLInputElement).value) / 100)" class="style-slider" />
                <span class="slider-value">{{ Math.round(styleOpacity * 100) }}%</span>
              </div>
            </div>
          </div>

          <!-- 历史面板 -->
          <div v-show="leftPanelTab === 'history'" class="history-panel">
            <div class="history-list">
              <div class="history-item">
                <i class="fa-solid fa-layer-group history-icon add"></i>
                <div class="history-info">
                  <span class="history-action">当前 {{ mapStore.sortedLayers.length }} 个图层</span>
                  <span class="history-time">图层树为实时数据</span>
                </div>
              </div>
              <div class="history-item">
                <i class="fa-solid fa-pen-to-square history-icon style"></i>
                <div class="history-info">
                  <span class="history-action">
                    未保存修改 {{ editStore.dirtyIds.length }} 个图层
                  </span>
                  <span class="history-time">编辑模式中 Ctrl+Z 撤销 / Ctrl+Y 重做</span>
                </div>
              </div>
              <div class="history-item">
                <i class="fa-solid fa-rotate-left history-icon zoom"></i>
                <div class="history-info">
                  <span class="history-action">
                    撤销栈 {{ totalUndoCount }} 条记录
                  </span>
                  <span class="history-time">在“编辑模式”面板操作</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 中央地图画布 -->
      <div class="qgis-map-canvas">
        <div class="map-container">
          <LegacyMapPanel :show-chrome="false" />
        </div>
        
        <!-- 地图悬浮工具 -->
        <div class="map-floating-tools">
          <button class="float-tool" title="全屏" @click="toggleFullscreen">
            <i class="fa-solid fa-expand"></i>
          </button>
          <button class="float-tool" title="刷新图层" @click="refreshMap">
            <i class="fa-solid fa-rotate"></i>
          </button>
        </div>

        <!-- 空间分析 / 任务参数浮动面板（编辑界面内复用，锚定到地图画布） -->
        <AnalysisPanel v-if="appStore.showAnalysisPanel" />
        <ParamsPanel v-if="appStore.showParamsPanel" />
      </div>

      <!-- 右侧面板 -->
      <div class="qgis-right-panel">
        <div class="panel-tabs">
          <button 
            class="panel-tab" 
            :class="{ active: rightPanelTab === 'processing' }"
            @click="rightPanelTab = 'processing'"
          >
            <i class="fa-solid fa-gears"></i>
            <span>处理工具箱</span>
          </button>
          <button 
            class="panel-tab" 
            :class="{ active: rightPanelTab === 'attributes' }"
            @click="rightPanelTab = 'attributes'"
          >
            <i class="fa-solid fa-table-list"></i>
            <span>属性</span>
          </button>
        </div>

        <div class="panel-content">
          <!-- 处理工具箱 -->
          <div v-show="rightPanelTab === 'processing'" class="processing-toolbox">
            <div class="toolbox-search">
              <i class="fa-solid fa-magnifying-glass"></i>
              <input type="text" placeholder="搜索工具..." v-model="toolboxSearch" />
            </div>

            <div class="toolbox-groups">
              <div class="toolbox-group" v-for="group in filteredToolboxGroups" :key="group.id">
                <div class="toolbox-group-header" @click="toggleToolboxGroup(group.id)">
                  <i :class="toolboxGroups[group.id] ? 'fa-solid fa-caret-down' : 'fa-solid fa-caret-right'"></i>
                  <i :class="group.icon + ' group-icon'"></i>
                  <span>{{ group.label }}</span>
                </div>
                <div class="toolbox-items" v-show="toolboxGroups[group.id]">
                  <div class="toolbox-item" v-for="item in group.items" :key="item.id" @click="runToolboxAction(item.action)">
                    <i :class="item.icon"></i>
                    <span>{{ item.label }}</span>
                  </div>
                </div>
              </div>
              <div v-if="filteredToolboxGroups.length === 0" class="toolbox-empty">
                未找到匹配的工具
              </div>
            </div>
          </div>

          <!-- 属性面板 -->
          <div v-show="rightPanelTab === 'attributes'" class="attributes-panel">
            <div class="attr-header">
              <span>要素属性</span>
              <span class="feature-count">{{ editStore.selectedFeatureInfo?.layerName || selectedLayerName }}</span>
            </div>
            <div v-if="editStore.selectedFeatureInfo" class="attr-content">
              <div class="attr-row" v-for="(value, key) in editStore.selectedFeatureInfo.properties" :key="key">
                <span class="attr-key">{{ key }}</span>
                <span class="attr-value">{{ formatAttrValue(value) }}</span>
              </div>
              <div v-if="Object.keys(editStore.selectedFeatureInfo.properties).length === 0" class="attr-empty">
                <i class="fa-solid fa-info-circle"></i>
                <p>该要素无属性</p>
              </div>
            </div>
            <div v-else class="attr-empty">
              <i class="fa-solid fa-mouse-pointer"></i>
              <p>点击地图上的要素查看其属性</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="qgis-status-bar">
      <div class="status-left">
        <span class="status-item">
          <i class="fa-solid fa-check-circle ok"></i>
          已就绪
        </span>
        <span class="status-item">
          投影: WGS84 / Web Mercator
        </span>
        <span class="status-item">
          {{ mapStore.sortedLayers.length }} 个图层
        </span>
      </div>
      <div class="status-center">
        <span class="status-item">
          比例尺: 1:{{ scale.toLocaleString() }}
        </span>
      </div>
      <div class="status-right">
        <span class="status-item">
          <i class="fa-solid fa-mouse-pointer"></i>
          {{ currentToolLabel }}
        </span>
        <span class="status-item">
          坐标: {{ centerLng }}, {{ centerLat }}
        </span>
      </div>
    </div>

    <!-- Toast 提示 -->
    <div class="qgis-toast" v-if="toastVisible">
      <i class="fa-solid fa-info-circle"></i>
      <span>{{ toastMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import LegacyMapPanel from './LegacyMapPanel.vue'
import AnalysisPanel from './AnalysisPanel.vue'
import ParamsPanel from './ParamsPanel.vue'
import { useAppStore } from '@/stores/appStore'
import { useMapStore } from '@/stores/mapStore'
import { useEditStore } from '@/stores/editStore'
import api from '@/services/api'
import { lonLatToWebMercator, webMercatorToLonLat, projectCoordsDeep } from '@/utils/analysis'
import { showInputDialog } from '@/utils/dialog'

const appStore = useAppStore()
const mapStore = useMapStore()
const editStore = useEditStore()

// 菜单数据
const menus = [
  {
    id: 'file',
    label: '文件',
    items: [
      { id: 'new', label: '新建工程', icon: 'fa-solid fa-file-circle-plus', shortcut: 'Ctrl+N' },
      { id: 'open', label: '打开工程', icon: 'fa-solid fa-folder-open', shortcut: 'Ctrl+O' },
      { id: 'save', label: '保存工程', icon: 'fa-solid fa-floppy-disk', shortcut: 'Ctrl+S' },
      { id: 'saveas', label: '另存为...', icon: 'fa-solid fa-floppy-disk', shortcut: 'Ctrl+Shift+S' },
      { id: 'sep1', type: 'separator' },
      { id: 'import', label: '导入数据', icon: 'fa-solid fa-file-import' },
      { id: 'export', label: '导出地图', icon: 'fa-solid fa-file-export' },
      { id: 'sep2', type: 'separator' },
      { id: 'print', label: '打印', icon: 'fa-solid fa-print', shortcut: 'Ctrl+P' },
      { id: 'sep3', type: 'separator' },
      { id: 'exit', label: '退出', icon: 'fa-solid fa-right-from-bracket' },
    ]
  },
  {
    id: 'edit',
    label: '编辑',
    items: [
      { id: 'undo', label: '撤销', icon: 'fa-solid fa-rotate-left', shortcut: 'Ctrl+Z' },
      { id: 'redo', label: '重做', icon: 'fa-solid fa-rotate-right', shortcut: 'Ctrl+Y' },
      { id: 'sep1', type: 'separator' },
      { id: 'cut', label: '剪切', icon: 'fa-solid fa-scissors', shortcut: 'Ctrl+X' },
      { id: 'copy', label: '复制', icon: 'fa-regular fa-copy', shortcut: 'Ctrl+C' },
      { id: 'paste', label: '粘贴', icon: 'fa-solid fa-paste', shortcut: 'Ctrl+V' },
      { id: 'deleteFeature', label: '删除要素', icon: 'fa-solid fa-trash', shortcut: 'Delete' },
      { id: 'sep2', type: 'separator' },
      { id: 'startEdit', label: '开始编辑会话', icon: 'fa-solid fa-pencil' },
      { id: 'saveEdit', label: '保存编辑', icon: 'fa-solid fa-check', shortcut: 'Ctrl+S' },
      { id: 'stopEdit', label: '停止编辑', icon: 'fa-solid fa-xmark' },
      { id: 'sep3', type: 'separator' },
      { id: 'selectAll', label: '全选', icon: 'fa-solid fa-check-double', shortcut: 'Ctrl+A' },
      { id: 'deselect', label: '取消选择', icon: 'fa-solid fa-eraser' },
      { id: 'selectByAttr', label: '按属性选择', icon: 'fa-solid fa-filter' },
    ]
  },
  {
    id: 'view',
    label: '视图',
    items: [
      { id: 'zoomIn', label: '放大', icon: 'fa-solid fa-magnifying-glass-plus', shortcut: '+' },
      { id: 'zoomOut', label: '缩小', icon: 'fa-solid fa-magnifying-glass-minus', shortcut: '-' },
      { id: 'zoomFull', label: '缩放到全图', icon: 'fa-solid fa-globe', shortcut: 'Ctrl+0' },
      { id: 'zoomLayer', label: '缩放到图层', icon: 'fa-solid fa-layer-group' },
      { id: 'sep1', type: 'separator' },
      { id: 'pan', label: '平移', icon: 'fa-solid fa-hand', shortcut: 'P' },
      { id: 'refresh', label: '刷新地图', icon: 'fa-solid fa-rotate' },
      { id: 'sep2', type: 'separator' },
      { id: 'fullscreen', label: '全屏', icon: 'fa-solid fa-expand', shortcut: 'F11' },
    ]
  },
  {
    id: 'map',
    label: '地图',
    items: [
      { id: 'addTitle', label: '添加图名', icon: 'fa-solid fa-heading' },
      { id: 'addLegend', label: '添加图例', icon: 'fa-solid fa-list' },
      { id: 'addScaleBar', label: '添加比例尺', icon: 'fa-solid fa-ruler-horizontal' },
      { id: 'addNorthArrow', label: '添加指北针', icon: 'fa-solid fa-compass' },
      { id: 'addInsetMap', label: '添加附图', icon: 'fa-solid fa-map' },
      { id: 'addText', label: '添加文字注记', icon: 'fa-solid fa-pen' },
      { id: 'sep1', type: 'separator' },
      { id: 'labelToggle', label: '标注开关', icon: 'fa-solid fa-font' },
      { id: 'autoLabel', label: '自动标注', icon: 'fa-solid fa-wand-magic-sparkles' },
    ]
  },
  {
    id: 'layer',
    label: '图层',
    items: [
      { id: 'addVector', label: '添加矢量图层', icon: 'fa-solid fa-draw-polygon' },
      { id: 'addRaster', label: '添加栅格图层', icon: 'fa-solid fa-image' },
      { id: 'addWMS', label: '添加WMS图层', icon: 'fa-solid fa-server' },
      { id: 'sep1', type: 'separator' },
      { id: 'newVector', label: '新建矢量图层', icon: 'fa-solid fa-plus' },
      { id: 'newShapefile', label: '新建Shapefile', icon: 'fa-regular fa-square-plus' },
      { id: 'sep2', type: 'separator' },
      { id: 'attrTable', label: '打开属性表', icon: 'fa-solid fa-table', shortcut: 'F6' },
    ]
  },
  {
    id: 'settings',
    label: '设置',
    items: [
      { id: 'options', label: '选项', icon: 'fa-solid fa-gear' },
      { id: 'projection', label: '投影设置', icon: 'fa-solid fa-earth-asia' },
      { id: 'styles', label: '样式管理器', icon: 'fa-solid fa-palette' },
      { id: 'sep1', type: 'separator' },
      { id: 'snapToggle', label: '捕捉设置', icon: 'fa-solid fa-magnet' },
      { id: 'snapTolerance', label: '捕捉容差', icon: 'fa-solid fa-sliders' },
    ]
  },
  {
    id: 'plugins',
    label: '插件',
    items: [
      { id: 'manage', label: '管理插件', icon: 'fa-solid fa-puzzle-piece' },
      { id: 'install', label: '安装插件', icon: 'fa-solid fa-download' },
    ]
  },
  {
    id: 'help',
    label: '帮助',
    items: [
      { id: 'docs', label: '文档', icon: 'fa-solid fa-book' },
      { id: 'about', label: '关于', icon: 'fa-solid fa-circle-info' },
    ]
  },
]

// 工具组定义
interface ToolItem {
  id: string
  icon: string
  title: string
}

interface ToolGroup {
  id: string
  label: string
  tools: ToolItem[]
}

// 所有可用的工具组
const allToolGroups: ToolGroup[] = [
  {
    id: 'file',
    label: '文件',
    tools: [
      { id: 'new', icon: 'fa-solid fa-file-circle-plus', title: '新建工程' },
      { id: 'open', icon: 'fa-solid fa-folder-open', title: '打开工程' },
      { id: 'save', icon: 'fa-solid fa-floppy-disk', title: '保存工程' },
      { id: 'print', icon: 'fa-solid fa-print', title: '打印' },
    ]
  },
  {
    id: 'edit',
    label: '编辑',
    tools: [
      { id: 'undo', icon: 'fa-solid fa-rotate-left', title: '撤销' },
      { id: 'redo', icon: 'fa-solid fa-rotate-right', title: '重做' },
      { id: 'cut', icon: 'fa-solid fa-scissors', title: '剪切' },
      { id: 'copy', icon: 'fa-regular fa-copy', title: '复制' },
      { id: 'paste', icon: 'fa-solid fa-paste', title: '粘贴' },
    ]
  },
  {
    id: 'navigation',
    label: '导航',
    tools: [
      { id: 'pan', icon: 'fa-solid fa-hand', title: '平移' },
      { id: 'zoomIn', icon: 'fa-solid fa-magnifying-glass-plus', title: '放大' },
      { id: 'zoomOut', icon: 'fa-solid fa-magnifying-glass-minus', title: '缩小' },
      { id: 'zoomFull', icon: 'fa-solid fa-globe', title: '缩放到全图' },
      { id: 'zoomLayer', icon: 'fa-solid fa-layer-group', title: '缩放到图层' },
      { id: 'prevView', icon: 'fa-solid fa-arrow-left', title: '上一视图' },
      { id: 'nextView', icon: 'fa-solid fa-arrow-right', title: '下一视图' },
    ]
  },
  {
    id: 'layer',
    label: '图层',
    tools: [
      { id: 'addVector', icon: 'fa-solid fa-draw-polygon', title: '添加矢量图层' },
      { id: 'addRaster', icon: 'fa-solid fa-image', title: '添加栅格图层' },
      { id: 'addWMS', icon: 'fa-solid fa-server', title: '添加WMS图层' },
      { id: 'newVector', icon: 'fa-solid fa-plus', title: '新建矢量图层' },
      { id: 'newShapefile', icon: 'fa-regular fa-square-plus', title: '新建Shapefile' },
    ]
  },
  {
    id: 'digitizing',
    label: '数字化',
    tools: [
      { id: 'startEdit', icon: 'fa-solid fa-pencil', title: '开始编辑' },
      { id: 'saveEdit', icon: 'fa-solid fa-check', title: '保存编辑' },
      { id: 'stopEdit', icon: 'fa-solid fa-xmark', title: '停止编辑' },
      { id: 'addPoint', icon: 'fa-solid fa-location-dot', title: '添加点要素' },
      { id: 'addLine', icon: 'fa-solid fa-minus', title: '添加线要素' },
      { id: 'addPolygon', icon: 'fa-regular fa-square', title: '添加面要素' },
      { id: 'moveFeature', icon: 'fa-solid fa-arrows-up-down-left-right', title: '移动要素' },
      { id: 'deleteFeature', icon: 'fa-solid fa-trash', title: '删除要素' },
    ]
  },
  {
    id: 'vertex',
    label: '顶点编辑',
    tools: [
      { id: 'nodeTool', icon: 'fa-solid fa-vector-square', title: '节点工具' },
      { id: 'addVertex', icon: 'fa-solid fa-plus', title: '添加节点' },
      { id: 'deleteVertex', icon: 'fa-solid fa-minus', title: '删除节点' },
      { id: 'moveVertex', icon: 'fa-solid fa-arrows-up-down-left-right', title: '移动节点' },
      { id: 'mergeVertex', icon: 'fa-solid fa-object-group', title: '合并节点' },
      { id: 'splitFeature', icon: 'fa-solid fa-scissors', title: '分割要素' },
      { id: 'mergeFeatures', icon: 'fa-solid fa-object-ungroup', title: '合并要素' },
    ]
  },
  {
    id: 'advancedEdit',
    label: '高级编辑',
    tools: [
      { id: 'rotate', icon: 'fa-solid fa-rotate', title: '旋转要素' },
      { id: 'scale', icon: 'fa-solid fa-expand', title: '缩放要素' },
      { id: 'mirror', icon: 'fa-solid fa-arrows-left-right', title: '镜像要素' },
      { id: 'offset', icon: 'fa-solid fa-arrows-turn-right', title: '偏移曲线' },
      { id: 'simplify', icon: 'fa-solid fa-wave-square', title: '简化要素' },
      { id: 'smooth', icon: 'fa-solid fa-wand-magic-sparkles', title: '平滑要素' },
      { id: 'buffer', icon: 'fa-solid fa-circle', title: '缓冲区' },
    ]
  },
  {
    id: 'selection',
    label: '选择',
    tools: [
      { id: 'selectRect', icon: 'fa-regular fa-square', title: '按矩形选择' },
      { id: 'selectPolygon', icon: 'fa-solid fa-draw-polygon', title: '按多边形选择' },
      { id: 'selectFree', icon: 'fa-solid fa-hand-dots', title: '按自由形状选择' },
      { id: 'selectRadius', icon: 'fa-regular fa-circle', title: '按半径选择' },
      { id: 'selectAll', icon: 'fa-solid fa-check-double', title: '全选' },
      { id: 'deselect', icon: 'fa-solid fa-eraser', title: '取消选择' },
    ]
  },
  {
    id: 'measure',
    label: '测量',
    tools: [
      { id: 'measureDistance', icon: 'fa-solid fa-ruler', title: '测量距离' },
      { id: 'measureArea', icon: 'fa-solid fa-ruler-combined', title: '测量面积' },
      { id: 'measureAngle', icon: 'fa-solid fa-angle', title: '测量角度' },
    ]
  },
  {
    id: 'georeferencing',
    label: '校准',
    tools: [
      { id: 'addControlPoint', icon: 'fa-solid fa-thumbtack', title: '添加控制点' },
      { id: 'deleteControlPoint', icon: 'fa-solid fa-xmark', title: '删除控制点' },
      { id: 'georeference', icon: 'fa-solid fa-earth-asia', title: '地理配准' },
      { id: 'transform', icon: 'fa-solid fa-arrows-rotate', title: '几何变换' },
      { id: 'warp', icon: 'fa-solid fa-image', title: '影像校正' },
      { id: 'adjust', icon: 'fa-solid fa-sliders', title: '调整大小' },
    ]
  },
  {
    id: 'spatialAnalysis',
    label: '空间分析',
    tools: [
      { id: 'bufferAnalysis', icon: 'fa-solid fa-circle', title: '缓冲区分析' },
      { id: 'overlay', icon: 'fa-solid fa-layer-group', title: '叠加分析' },
      { id: 'clip', icon: 'fa-solid fa-cut', title: '裁剪' },
      { id: 'union', icon: 'fa-solid fa-object-group', title: '合并' },
      { id: 'intersect', icon: 'fa-solid fa-shapes', title: '相交' },
      { id: 'symDiff', icon: 'fa-solid fa-shuffle', title: '对称差' },
    ]
  },
  {
    id: 'shapeDigitizing',
    label: '形状数字化',
    tools: [
      { id: 'addRect', icon: 'fa-regular fa-square', title: '添加矩形' },
      { id: 'addCircle', icon: 'fa-regular fa-circle', title: '添加圆形' },
      { id: 'addEllipse', icon: 'fa-solid fa-circle-notch', title: '添加椭圆' },
      { id: 'addHeart', icon: 'fa-solid fa-heart', title: '添加心形' },
    ]
  },
  {
    id: 'snapping',
    label: '捕捉',
    tools: [
      { id: 'snapToggle', icon: 'fa-solid fa-magnet', title: '捕捉开关' },
      { id: 'snapVertex', icon: 'fa-solid fa-circle-dot', title: '捕捉到顶点' },
      { id: 'snapEdge', icon: 'fa-solid fa-minus', title: '捕捉到边' },
      { id: 'snapIntersection', icon: 'fa-solid fa-xmark', title: '捕捉到交点' },
      { id: 'snapTolerance', icon: 'fa-solid fa-sliders', title: '捕捉容差设置' },
    ]
  },
  {
    id: 'labeling',
    label: '标注',
    tools: [
      { id: 'labelToggle', icon: 'fa-solid fa-font', title: '标注开关' },
      { id: 'labelField', icon: 'fa-solid fa-tag', title: '标注字段选择' },
      { id: 'labelStyle', icon: 'fa-solid fa-palette', title: '标注样式' },
      { id: 'labelPlacement', icon: 'fa-solid fa-arrows-up-down-left-right', title: '标注放置' },
      { id: 'autoLabel', icon: 'fa-solid fa-wand-magic-sparkles', title: '自动标注' },
    ]
  },
  {
    id: 'attributes',
    label: '属性',
    tools: [
      { id: 'identify', icon: 'fa-solid fa-circle-info', title: '识别要素' },
      { id: 'fieldCalc', icon: 'fa-solid fa-calculator', title: '字段计算器' },
      { id: 'statistics', icon: 'fa-solid fa-chart-simple', title: '统计摘要' },
      { id: 'selectByAttr', icon: 'fa-solid fa-filter', title: '按属性选择' },
    ]
  },
  {
    id: 'mapDecoration',
    label: '地图整饰',
    tools: [
      { id: 'addTitle', icon: 'fa-solid fa-heading', title: '添加图名' },
      { id: 'addLegend', icon: 'fa-solid fa-list', title: '添加图例' },
      { id: 'addScaleBar', icon: 'fa-solid fa-ruler-horizontal', title: '添加比例尺' },
      { id: 'addNorthArrow', icon: 'fa-solid fa-compass', title: '添加指北针' },
      { id: 'addInsetMap', icon: 'fa-solid fa-map', title: '添加附图' },
      { id: 'addText', icon: 'fa-solid fa-pen', title: '添加文字注记' },
    ]
  },
  {
    id: 'raster',
    label: '栅格分析',
    tools: [
      { id: 'hillshade', icon: 'fa-solid fa-mountain', title: 'DEM山体阴影' },
      { id: 'contour', icon: 'fa-solid fa-wave-square', title: '等高线提取' },
      { id: 'slope', icon: 'fa-solid fa-chart-line', title: '坡度分析' },
      { id: 'aspect', icon: 'fa-solid fa-compass', title: '坡向分析' },
      { id: 'rasterCalc', icon: 'fa-solid fa-square-root-variable', title: '栅格计算器' },
    ]
  },
]

// 当前显示的工具组ID列表
const activeToolGroupIds = ref<string[]>(['file', 'edit', 'navigation', 'layer', 'digitizing', 'shapeDigitizing', 'vertex', 'advancedEdit', 'selection', 'snapping', 'labeling', 'attributes', 'measure', 'mapDecoration', 'raster'])

// 工具组选择器显示状态
const showToolGroupSelector = ref(false)

// 切换工具组显示状态
function toggleToolGroup(groupId: string) {
  const index = activeToolGroupIds.value.indexOf(groupId)
  if (index > -1) {
    activeToolGroupIds.value.splice(index, 1)
  } else {
    activeToolGroupIds.value.push(groupId)
  }
}

// 获取当前显示的工具组
const activeToolGroups = computed(() => {
  return allToolGroups.filter(g => activeToolGroupIds.value.includes(g.id))
})

// 状态
const leftPanelTab = ref<'layers' | 'style' | 'history'>('layers')
const rightPanelTab = ref<'processing' | 'attributes'>('processing')
const selectedLayer = ref<string | null>(null)
const activeTool = ref('pan')
const isEditing = ref(false)
const scale = ref(50000)
const toastVisible = ref(false)
const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// 样式编辑
const renderMode = ref('单点渲染')
const styleFill = ref('#3b82f6')
const styleColor = ref('#1e40af')
const styleWeight = ref(1)
const styleOpacity = ref(1)

const selectedLayerName = computed(() => {
  if (!selectedLayer.value) return '未选择图层'
  return mapStore.layerGroups[selectedLayer.value]?.data.name || '未选择图层'
})

const totalUndoCount = computed(() =>
  Object.values(editStore.undoStack).reduce((s, arr) => s + (arr?.length || 0), 0)
)

const centerLat = computed(() =>
  (mapStore.currentMapData?.center?.[0] ?? 30.5928).toFixed(4)
)

const centerLng = computed(() =>
  (mapStore.currentMapData?.center?.[1] ?? 114.3055).toFixed(4)
)

/** 图层树：按 group 分组，保持图层显示顺序（order 升序） */
const groupedLayerTree = computed(() => {
  const groups: { name: string; layers: any[] }[] = []
  const index: Record<string, { name: string; layers: any[] }> = {}
  mapStore.sortedLayers.forEach((layer) => {
    const g = layer.data.group || ''
    if (!index[g]) {
      index[g] = { name: g, layers: [] }
      groups.push(index[g])
    }
    index[g].layers.push(layer)
  })
  return groups
})

const toolboxGroups = ref<Record<string, boolean>>({
  geo: true,
  analysis: false,
  conversion: false,
})

// 处理工具箱数据（支持搜索过滤）
const toolboxSearch = ref('')

interface ToolboxEntry {
  id: string
  group: 'geo' | 'analysis' | 'conversion'
  icon: string
  label: string
  action: string
}

const toolboxItems: ToolboxEntry[] = [
  { id: 'buffer', group: 'geo', icon: 'fa-solid fa-circle-dot', label: '缓冲区', action: 'buffer' },
  { id: 'overlay', group: 'geo', icon: 'fa-solid fa-layer-group', label: '叠加分析', action: 'overlay' },
  { id: 'clip', group: 'geo', icon: 'fa-solid fa-scissors', label: '裁剪', action: 'clip' },
  { id: 'intersect', group: 'geo', icon: 'fa-solid fa-object-group', label: '相交', action: 'intersect' },
  { id: 'union', group: 'geo', icon: 'fa-solid fa-shapes', label: '并集', action: 'union' },
  { id: 'nearest', group: 'analysis', icon: 'fa-solid fa-ruler', label: '最近邻', action: 'nearest' },
  { id: 'density', group: 'analysis', icon: 'fa-solid fa-chart-area', label: '密度分析', action: 'density' },
  { id: 'export', group: 'conversion', icon: 'fa-solid fa-file-export', label: '格式转换（导出）', action: 'export' },
  { id: 'projection', group: 'conversion', icon: 'fa-solid fa-earth-asia', label: '投影转换', action: 'projection' },
]

const toolboxGroupMeta: Record<string, { label: string; icon: string }> = {
  geo: { label: '地理处理', icon: 'fa-solid fa-globe' },
  analysis: { label: '空间分析', icon: 'fa-solid fa-chart-line' },
  conversion: { label: '数据转换', icon: 'fa-solid fa-right-left' },
}

const filteredToolboxGroups = computed(() => {
  const kw = toolboxSearch.value.trim().toLowerCase()
  const filtered = kw
    ? toolboxItems.filter((it) => it.label.toLowerCase().includes(kw))
    : toolboxItems
  return (['geo', 'analysis', 'conversion'] as const)
    .map((gid) => ({
      id: gid,
      label: toolboxGroupMeta[gid].label,
      icon: toolboxGroupMeta[gid].icon,
      items: filtered.filter((it) => it.group === gid),
    }))
    .filter((g) => g.items.length > 0)
})

function runToolboxAction(action: string) {
  if (action === 'buffer') { openAnalysis('buffer'); return }
  if (action === 'overlay') { openAnalysis('overlay'); return }
  if (action === 'clip') { openAnalysis('clip'); return }
  if (action === 'intersect') { openAnalysis('intersect'); return }
  if (action === 'union') { openAnalysis('union'); return }
  if (action === 'nearest') { openAnalysis('nearest'); return }
  if (action === 'density') { runDensityAnalysis(); return }
  if (action === 'export') { openExportMenu(); return }
  if (action === 'projection') { runProjection(); return }
  showToast(action)
}

// 工具中文标签（顶栏与菜单共用的唯一映射，缺省时不再显示“未知工具”）
const toolLabels: Record<string, string> = {
  // 文件
  new: '新建工程',
  open: '打开工程',
  save: '保存工程',
  saveas: '另存为',
  import: '导入数据',
  export: '导出地图',
  print: '打印',
  exit: '退出',
  // 编辑
  undo: '撤销',
  redo: '重做',
  cut: '剪切',
  copy: '复制',
  paste: '粘贴',
  selectAll: '全选',
  deselect: '取消选择',
  // 视图 / 导航
  pan: '平移工具',
  zoomIn: '放大工具',
  zoomOut: '缩小工具',
  zoomFull: '全图缩放',
  zoomLayer: '缩放至图层',
  prevView: '上一视图',
  nextView: '下一视图',
  fullscreen: '全屏',
  // 图层
  addVector: '添加矢量图层',
  addRaster: '添加栅格图层',
  addWMS: '添加WMS图层',
  newVector: '新建矢量图层',
  newShapefile: '新建Shapefile',
  attrTable: '属性表',
  // 数字化
  startEdit: '开始编辑',
  saveEdit: '保存编辑',
  stopEdit: '停止编辑',
  addPoint: '添加点',
  addLine: '添加线',
  addPolygon: '添加面',
  moveFeature: '移动要素',
  deleteFeature: '删除要素',
  // 顶点编辑
  nodeTool: '节点工具',
  addVertex: '添加节点',
  deleteVertex: '删除节点',
  moveVertex: '移动节点',
  mergeVertex: '合并节点',
  splitFeature: '分割要素',
  mergeFeatures: '合并要素',
  // 高级编辑
  rotate: '旋转要素',
  scale: '缩放要素',
  mirror: '镜像要素',
  offset: '偏移曲线',
  simplify: '简化要素',
  smooth: '平滑要素',
  buffer: '缓冲区',
  // 选择
  selectRect: '矩形选择',
  selectPolygon: '多边形选择',
  selectFree: '自由选择',
  selectRadius: '半径选择',
  // 测量
  measureDistance: '测量距离',
  measureArea: '测量面积',
  measureAngle: '测量角度',
  // 校准
  addControlPoint: '添加控制点',
  deleteControlPoint: '删除控制点',
  georeference: '地理配准',
  transform: '几何变换',
  warp: '影像校正',
  adjust: '调整大小',
  // 空间分析
  bufferAnalysis: '缓冲区分析',
  overlay: '叠加分析',
  clip: '裁剪',
  intersect: '相交',
  union: '合并',
  symDiff: '对称差',
  // 设置 / 插件 / 帮助
  options: '选项',
  projection: '投影设置',
  styles: '样式管理器',
  manage: '管理插件',
  install: '安装插件',
  docs: '文档',
  about: '关于',
  // 形状数字化
  addRect: '添加矩形',
  addCircle: '添加圆形',
  addEllipse: '添加椭圆',
  addHeart: '添加心形',
  // 捕捉
  snapToggle: '捕捉开关',
  snapVertex: '捕捉到顶点',
  snapEdge: '捕捉到边',
  snapIntersection: '捕捉到交点',
  snapTolerance: '捕捉容差设置',
  // 标注
  labelToggle: '标注开关',
  labelField: '标注字段选择',
  labelStyle: '标注样式',
  labelPlacement: '标注放置',
  autoLabel: '自动标注',
  // 属性
  identify: '识别要素',
  fieldCalc: '字段计算器',
  statistics: '统计摘要',
  selectByAttr: '按属性选择',
  // 地图整饰
  addTitle: '添加图名',
  addLegend: '添加图例',
  addScaleBar: '添加比例尺',
  addNorthArrow: '添加指北针',
  addInsetMap: '添加附图',
  addText: '添加文字注记',
  // 栅格分析
  hillshade: 'DEM山体阴影',
  contour: '等高线提取',
  slope: '坡度分析',
  aspect: '坡向分析',
  rasterCalc: '栅格计算器',
}

// 计算属性
const currentToolLabel = computed(() => toolLabels[activeTool.value] || '未激活工具')

// 方法
function setActiveTool(tool: string) {
  activeTool.value = tool
  showToast(`切换到${currentToolLabel.value}`)
}

/**
 * 模式类工具：点击后保持激活态（高亮），直到切换/取消，如平移、绘制、测量、选择、节点编辑。
 * 未列出的其余工具均为动作类：点击即执行一次，不保持激活（参考 QGIS 工具栏交互）。
 */
const TOOL_KINDS: Record<string, 'tool' | 'action'> = {
  pan: 'tool',
  selectRect: 'tool',
  selectPolygon: 'tool',
  selectFree: 'tool',
  selectRadius: 'tool',
  addPoint: 'tool',
  addLine: 'tool',
  addPolygon: 'tool',
  nodeTool: 'tool',
  moveFeature: 'tool',
  addVertex: 'tool',
  deleteVertex: 'tool',
  moveVertex: 'tool',
  addControlPoint: 'tool',
  deleteControlPoint: 'tool',
  measureDistance: 'tool',
  measureArea: 'tool',
  measureAngle: 'tool',
  // 形状数字化（模式工具：点击后保持激活，用于绘制规则形状）
  addRect: 'tool',
  addCircle: 'tool',
  addEllipse: 'tool',
  addHeart: 'tool',
  // 识别要素（模式工具）
  identify: 'tool',
  // 按属性选择（模式工具）
  selectByAttr: 'tool',
}

/** 动作类工具执行完成后的反馈文案 */
const ACTION_TOASTS: Record<string, string> = {
  save: '地图已保存：PNG 文件已下载到本地',
  saveEdit: '编辑内容已保存',
  undo: '已撤销上一步',
  redo: '已恢复下一步',
  cut: '已复制选中要素',
  copy: '已复制选中要素',
  paste: '已粘贴要素',
  deleteFeature: '已删除选中要素',
  simplify: '已简化选中要素',
  smooth: '已平滑选中要素',
  selectAll: '已全选要素',
  deselect: '已清除选择',
  zoomIn: '已放大',
  zoomOut: '已缩小',
  zoomFull: '已缩放到全图',
  zoomLayer: '已缩放到选中图层',
  prevView: '已切换到上一视图',
  nextView: '已切换到下一视图',
  mergeVertex: '已合并节点',
  splitFeature: '已分割要素',
  mergeFeatures: '已合并要素',
  rotate: '已旋转选中要素',
  scale: '已缩放选中要素',
  mirror: '已镜像选中要素',
  offset: '已偏移选中要素',
  transform: '已执行几何变换',
  adjust: '已调整大小',
  buffer: '已打开缓冲区分析',
  bufferAnalysis: '已打开缓冲区分析',
  overlay: '已打开叠加分析',
  clip: '已打开裁剪分析',
  union: '已打开合并分析',
  intersect: '已打开相交分析',
  symDiff: '已打开对称差分析',
  print: '已发送打印任务',
  // 捕捉
  snapToggle: '捕捉已切换',
  snapVertex: '已切换顶点捕捉',
  snapEdge: '已切换边捕捉',
  snapIntersection: '已切换交点捕捉',
  snapTolerance: '已打开捕捉容差设置',
  // 标注
  labelToggle: '标注已切换',
  labelField: '已打开标注字段选择',
  labelStyle: '已打开标注样式设置',
  labelPlacement: '已打开标注放置设置',
  autoLabel: '已执行自动标注',
  // 属性
  fieldCalc: '已打开字段计算器',
  statistics: '已生成统计摘要',
  // 地图整饰
  addTitle: '已添加图名',
  addLegend: '已添加图例',
  addScaleBar: '已添加比例尺',
  addNorthArrow: '已添加指北针',
  addInsetMap: '已添加附图',
  addText: '已添加文字注记',
  // 栅格分析
  hillshade: '已生成DEM山体阴影',
  contour: '已提取等高线',
  slope: '已生成坡度分析',
  aspect: '已生成坡向分析',
  rasterCalc: '已打开栅格计算器',
}

/** 动作类工具点击后调用：不切换激活工具，只给出完成反馈 */
function finishToolClick(toolId: string) {
  if (TOOL_KINDS[toolId] === 'tool') {
    setActiveTool(toolId)
    return
  }
  const msg = ACTION_TOASTS[toolId]
  if (msg) showToast(msg)
}

/** 保存地图文件：先保存当前编辑，再导出 PNG 下载到本地文件夹 */
async function saveMapFile() {
  if (!mapStore.currentMapId) {
    showToast('请先生成地图')
    return
  }
  try {
    dispatchMapEvent('map-edit-save')
    const resp = await api.exportMap(mapStore.currentMapId, 'png')
    const data = resp.data || resp
    const filename = `map-${Date.now()}.png`
    if (typeof data === 'string' && data.startsWith('data:')) {
      const link = document.createElement('a')
      link.href = data
      link.download = filename
      link.click()
    } else {
      const blob = new Blob([String(data)], { type: 'image/png' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    }
    showToast('地图已保存：PNG 文件已下载到本地')
  } catch (e: any) {
    showToast('保存失败: ' + (e.message || e))
  }
}

// 处理工具按钮点击
async function handleToolClick(tool: ToolItem) {
  // 编辑会话开关
  if (tool.id === 'startEdit') { toggleEditing(); return }
  if (tool.id === 'saveEdit') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-save'); finishToolClick(tool.id); return }
  if (tool.id === 'stopEdit') { if (appStore.showEditPanel) appStore.toggleEditPanel(); showToast('已停止编辑'); return }

  // 绘制工具 -> 编辑引擎
  const editToolMap: Record<string, string> = { addPoint: 'point', addLine: 'line', addPolygon: 'polygon' }
  if (editToolMap[tool.id]) {
    appStore.showEditPanel = true
    editStore.setDrawTool(editToolMap[tool.id] as 'point' | 'line' | 'polygon')
    dispatchMapEvent('map-edit-draw', { tool: editToolMap[tool.id] })
    setActiveTool(tool.id)
    return
  }

  // 删除 / 复制 / 剪切 / 粘贴 / 简化 / 平滑 / 撤销 / 重做
  if (tool.id === 'deleteFeature') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-delete'); finishToolClick(tool.id); return }
  if (tool.id === 'copy' || tool.id === 'cut') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-copy'); finishToolClick(tool.id); return }
  if (tool.id === 'paste') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-paste'); finishToolClick(tool.id); return }
  if (tool.id === 'simplify') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-simplify'); finishToolClick(tool.id); return }
  if (tool.id === 'smooth') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-smooth'); finishToolClick(tool.id); return }
  if (tool.id === 'undo') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-undo'); finishToolClick(tool.id); return }
  if (tool.id === 'redo') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-redo'); finishToolClick(tool.id); return }

  // 顶点/节点编辑工具 -> 进入编辑模式后点击要素即可拖拽节点（leaflet-editable）
  if (['nodeTool', 'addVertex', 'deleteVertex', 'moveVertex', 'moveFeature'].includes(tool.id)) {
    appStore.showEditPanel = true
    editStore.setStatus('节点编辑：点击要素选中后拖拽节点')
    setActiveTool(tool.id)
    return
  }

  // 测量（距离 / 面积 / 角度）
  if (tool.id === 'measureDistance') { dispatchMapEvent('map-measure-start', { mode: 'distance' }); setActiveTool(tool.id); return }
  if (tool.id === 'measureArea') { dispatchMapEvent('map-measure-start', { mode: 'area' }); setActiveTool(tool.id); return }
  if (tool.id === 'measureAngle') { dispatchMapEvent('map-measure-start', { mode: 'angle' }); setActiveTool(tool.id); return }

  // 选择工具 -> 进入编辑模式后点击要素选中
  if (tool.id.startsWith('select') && tool.id !== 'selectAll') {
    appStore.showEditPanel = true
    editStore.setStatus('选择要素：点击地图上的要素进行选择')
    setActiveTool(tool.id)
    return
  }
  if (tool.id === 'selectAll') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-select-all'); finishToolClick(tool.id); return }
  if (tool.id === 'deselect') { dispatchMapEvent('map-edit-clear-selection'); finishToolClick(tool.id); return }

  // 视图导航
  const mapEvents: Record<string, string> = { zoomIn: 'map-zoom-in', zoomOut: 'map-zoom-out', zoomFull: 'map-zoom-full' }
  if (mapEvents[tool.id]) { dispatchMapEvent(mapEvents[tool.id]); finishToolClick(tool.id); return }
  if (tool.id === 'prevView') { dispatchMapEvent('map-view-prev'); finishToolClick(tool.id); return }
  if (tool.id === 'nextView') { dispatchMapEvent('map-view-next'); finishToolClick(tool.id); return }
  if (tool.id === 'zoomLayer') { zoomToSelectedLayer(); finishToolClick(tool.id); return }
  if (tool.id === 'pan') { setActiveTool(tool.id); return }

  // 空间分析工具组 -> 复用 AnalysisPanel（缓冲/点面叠加）
  if (['buffer', 'bufferAnalysis'].includes(tool.id)) { appStore.setAnalysisMode('buffer'); finishToolClick(tool.id); return }
  if (['overlay', 'clip', 'intersect', 'union', 'symDiff'].includes(tool.id)) { appStore.setAnalysisMode('overlay'); finishToolClick(tool.id); return }

  // 图层工具
  if (['addVector', 'newVector', 'newShapefile'].includes(tool.id)) { addLayerByDialog(); return }
  if (['addRaster', 'addWMS'].includes(tool.id)) { showToast('栅格/WMS 图层暂不支持，请使用导入或矢量图层'); return }

  // 几何变换（旋转 / 缩放 / 镜像 / 偏移 / 合并节点 / 分割 / 合并）
  if (tool.id === 'rotate') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '旋转角度（度，正值顺时针）', defaultValue: '45' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-edit-rotate', { angle: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'scale') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '缩放比例（1.5 放大 / 0.5 缩小）', defaultValue: '1.5' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-edit-scale', { factor: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'mirror') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '镜像方向（h=水平 / v=垂直）', defaultValue: 'h' })
    if (v !== null) { dispatchMapEvent('map-edit-mirror', { axis: (v || 'h').toLowerCase().startsWith('v') ? 'vertical' : 'horizontal' }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'offset') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '偏移距离（米）', defaultValue: '500' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-edit-offset', { distance: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'mergeVertex') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-merge-vertex'); finishToolClick(tool.id); return }
  if (tool.id === 'splitFeature') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-split'); finishToolClick(tool.id); return }
  if (tool.id === 'mergeFeatures') { appStore.showEditPanel = true; dispatchMapEvent('map-edit-merge'); finishToolClick(tool.id); return }

  // 校准工具组（矢量制图场景：映射到节点编辑与仿射变换）
  if (['addControlPoint', 'addVertex'].includes(tool.id)) { appStore.showEditPanel = true; editStore.setStatus('添加控制点：点击要素后在节点间插入'); setActiveTool(tool.id); return }
  if (['deleteControlPoint', 'deleteVertex'].includes(tool.id)) { appStore.showEditPanel = true; editStore.setStatus('删除控制点：选中要素后删除节点'); setActiveTool(tool.id); return }
  if (tool.id === 'transform') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '仿射变换缩放比例', defaultValue: '1.2' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-edit-scale', { factor: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'adjust') {
    appStore.showEditPanel = true
    const v = await showInputDialog({ title: '调整缩放比例', defaultValue: '1.1' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-edit-scale', { factor: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (['georeference', 'warp'].includes(tool.id)) { showToast('矢量数据已带坐标，无需栅格配准/影像校正'); return }

  // ===== 形状数字化工具（规则形状绘制）=====
  const shapeToolMap: Record<string, string> = { addRect: 'rect', addCircle: 'circle', addEllipse: 'ellipse', addHeart: 'heart' }
  if (shapeToolMap[tool.id]) {
    appStore.showEditPanel = true
    editStore.setDrawTool('polygon')
    editStore.setShapeConstraint(shapeToolMap[tool.id])
    dispatchMapEvent('map-edit-draw-shape', { shape: shapeToolMap[tool.id] })
    setActiveTool(tool.id)
    return
  }

  // ===== 捕捉工具 =====
  if (tool.id === 'snapToggle') { editStore.toggleSnapping(); finishToolClick(tool.id); return }
  if (tool.id === 'snapVertex') { editStore.toggleSnapMode('vertex'); finishToolClick(tool.id); return }
  if (tool.id === 'snapEdge') { editStore.toggleSnapMode('edge'); finishToolClick(tool.id); return }
  if (tool.id === 'snapIntersection') { editStore.toggleSnapMode('intersection'); finishToolClick(tool.id); return }
  if (tool.id === 'snapTolerance') {
    const v = await showInputDialog({ title: '捕捉容差（像素）', defaultValue: '10' })
    if (v !== null && v.trim() !== '') { editStore.setSnapTolerance(parseInt(v)); finishToolClick(tool.id) }
    return
  }

  // ===== 标注工具 =====
  if (tool.id === 'labelToggle') { dispatchMapEvent('map-label-toggle'); finishToolClick(tool.id); return }
  if (tool.id === 'labelField') {
    const v = await showInputDialog({ title: '输入标注字段名（如 name）', defaultValue: 'name' })
    if (v !== null) { dispatchMapEvent('map-label-field', { field: v.trim() }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'labelStyle') { leftPanelTab.value = 'style'; showToast('请在样式面板调整标注样式'); return }
  if (tool.id === 'labelPlacement') {
    const v = await showInputDialog({ title: '标注放置方式（center/above/below/left/right）', defaultValue: 'center' })
    if (v !== null) { dispatchMapEvent('map-label-placement', { placement: v.trim() }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'autoLabel') { dispatchMapEvent('map-label-auto'); finishToolClick(tool.id); return }

  // ===== 属性工具 =====
  if (tool.id === 'identify') { setActiveTool(tool.id); editStore.setStatus('识别要素：点击地图上的要素查看属性'); return }
  if (tool.id === 'fieldCalc') {
    const v = await showInputDialog({ title: '字段计算器：输入表达式（如 area * 2）', defaultValue: '' })
    if (v !== null) { dispatchMapEvent('map-field-calc', { expression: v }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'statistics') { dispatchMapEvent('map-statistics'); finishToolClick(tool.id); return }
  if (tool.id === 'selectByAttr') {
    const v = await showInputDialog({ title: '按属性选择：输入条件（如 name LIKE "%区%"）', defaultValue: '' })
    if (v !== null) { dispatchMapEvent('map-select-by-attr', { condition: v }); setActiveTool(tool.id) }
    return
  }

  // ===== 地图整饰工具 =====
  if (tool.id === 'addTitle') {
    const v = await showInputDialog({ title: '输入图名', defaultValue: '地图标题' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-decoration-title', { text: v.trim() }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'addLegend') { dispatchMapEvent('map-decoration-legend'); finishToolClick(tool.id); return }
  if (tool.id === 'addScaleBar') { dispatchMapEvent('map-decoration-scalebar'); finishToolClick(tool.id); return }
  if (tool.id === 'addNorthArrow') { dispatchMapEvent('map-decoration-northarrow'); finishToolClick(tool.id); return }
  if (tool.id === 'addInsetMap') { dispatchMapEvent('map-decoration-inset'); finishToolClick(tool.id); return }
  if (tool.id === 'addText') {
    const v = await showInputDialog({ title: '输入文字注记内容', defaultValue: '' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-decoration-text', { text: v.trim() }); finishToolClick(tool.id) }
    return
  }

  // ===== 栅格分析工具 =====
  if (tool.id === 'hillshade') { dispatchMapEvent('map-raster-hillshade'); finishToolClick(tool.id); return }
  if (tool.id === 'contour') {
    const v = await showInputDialog({ title: '等高距（米）', defaultValue: '50' })
    if (v !== null && v.trim() !== '') { dispatchMapEvent('map-raster-contour', { interval: parseFloat(v) }); finishToolClick(tool.id) }
    return
  }
  if (tool.id === 'slope') { dispatchMapEvent('map-raster-slope'); finishToolClick(tool.id); return }
  if (tool.id === 'aspect') { dispatchMapEvent('map-raster-aspect'); finishToolClick(tool.id); return }
  if (tool.id === 'rasterCalc') {
    const v = await showInputDialog({ title: '栅格计算器：输入表达式（如 dem * 0.3048）', defaultValue: '' })
    if (v !== null) { dispatchMapEvent('map-raster-calc', { expression: v }); finishToolClick(tool.id) }
    return
  }

  // 文件
  if (tool.id === 'save') { await saveMapFile(); return }
  if (tool.id === 'new') { showToast('新建工程：请返回主界面开启新会话'); return }
  if (tool.id === 'open') { showToast('打开工程：请通过主界面历史记录加载会话'); return }
  if (tool.id === 'print') { window.print(); showToast('已发送打印任务'); return }

  // 高级几何变换 / 校准 / 栅格处理等专业 GIS 功能（明确提示暂未实现）
  showToast(`「${tool.title}」暂未实现`)
}

function toggleEditing() {
  appStore.toggleEditPanel()
  isEditing.value = appStore.showEditPanel
  showToast(isEditing.value ? '编辑模式已开启' : '已退出编辑模式')
}

function toggleToolboxGroup(group: string) {
  toolboxGroups.value[group] = !toolboxGroups.value[group]
}

function handleMenuAction(item: any) {
  const actions: Record<string, () => void> = {
    // 文件
    save: () => dispatchMapEvent('map-edit-save'),
    saveas: () => dispatchMapEvent('map-edit-save'),
    export: () => openExportMenu(),
    import: () => appStore.toggleImportModal(),
    print: () => window.print(),
    exit: () => goBack(),
    new: () => goBack(),
    open: () => appStore.toggleSessionDrawer(),
    // 编辑
    undo: () => dispatchMapEvent('map-edit-undo'),
    redo: () => dispatchMapEvent('map-edit-redo'),
    cut: () => dispatchMapEvent('map-edit-copy'),
    copy: () => dispatchMapEvent('map-edit-copy'),
    paste: () => dispatchMapEvent('map-edit-paste'),
    deleteFeature: () => { appStore.showEditPanel = true; dispatchMapEvent('map-edit-delete') },
    startEdit: () => toggleEditing(),
    saveEdit: () => { appStore.showEditPanel = true; dispatchMapEvent('map-edit-save') },
    stopEdit: () => { if (appStore.showEditPanel) appStore.toggleEditPanel(); showToast('已停止编辑') },
    selectAll: () => { appStore.showEditPanel = true; dispatchMapEvent('map-edit-select-all') },
    deselect: () => dispatchMapEvent('map-edit-clear-selection'),
    selectByAttr: () => handleToolClick({ id: 'selectByAttr', title: '按属性选择' } as ToolItem),
    // 视图
    zoomIn: () => dispatchMapEvent('map-zoom-in'),
    zoomOut: () => dispatchMapEvent('map-zoom-out'),
    zoomFull: () => dispatchMapEvent('map-zoom-full'),
    zoomLayer: () => zoomToSelectedLayer(),
    pan: () => setActiveTool('pan'),
    refresh: () => refreshMap(),
    fullscreen: () => toggleFullscreen(),
    // 地图整饰
    addTitle: () => handleToolClick({ id: 'addTitle', title: '添加图名' } as ToolItem),
    addLegend: () => handleToolClick({ id: 'addLegend', title: '添加图例' } as ToolItem),
    addScaleBar: () => handleToolClick({ id: 'addScaleBar', title: '添加比例尺' } as ToolItem),
    addNorthArrow: () => handleToolClick({ id: 'addNorthArrow', title: '添加指北针' } as ToolItem),
    addInsetMap: () => handleToolClick({ id: 'addInsetMap', title: '添加附图' } as ToolItem),
    addText: () => handleToolClick({ id: 'addText', title: '添加文字注记' } as ToolItem),
    labelToggle: () => handleToolClick({ id: 'labelToggle', title: '标注开关' } as ToolItem),
    autoLabel: () => handleToolClick({ id: 'autoLabel', title: '自动标注' } as ToolItem),
    // 图层
    addVector: () => addLayerByDialog(),
    addRaster: () => showToast('栅格图层暂不支持，请使用导入或矢量图层'),
    addWMS: () => showToast('WMS 图层暂不支持'),
    newVector: () => addLayerByDialog(),
    newShapefile: () => addLayerByDialog(),
    attrTable: () => openAttrTable(),
    // 设置
    options: () => appStore.toggleSettings(),
    projection: () => appStore.toggleParamsPanel(),
    styles: () => { leftPanelTab.value = 'style' },
    snapToggle: () => handleToolClick({ id: 'snapToggle', title: '捕捉开关' } as ToolItem),
    snapTolerance: () => handleToolClick({ id: 'snapTolerance', title: '捕捉容差设置' } as ToolItem),
    // 插件 / 帮助
    manage: () => showToast('插件管理暂不支持'),
    install: () => showToast('插件安装暂不支持'),
    docs: () => window.open('https://leafletjs.com', '_blank'),
    about: () => showToast('CartoAgent 地图制图智能体'),
    // 兼容
    metadata: () => appStore.toggleMetadataModal(),
    params: () => appStore.toggleParamsPanel(),
    addLayer: () => addLayerByDialog(),
  }
  const fn = actions[item.id]
  if (fn) fn()
  else showToast(item.label)
}

function showToast(message: string) {
  toastMessage.value = message
  toastVisible.value = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastVisible.value = false
    toastTimer = null
  }, 2000)
}

function goBack() {
  appStore.switchToMainView()
}

function dispatchMapEvent(name: string, detail?: any) {
  const el = document.getElementById('map-container')
  if (el) {
    el.dispatchEvent(new CustomEvent(name, detail !== undefined ? { detail } : undefined))
  }
}

async function addLayerByDialog() {
  if (!mapStore.currentMapId) {
    showToast('请先生成地图')
    return
  }
  const name = await showInputDialog({ title: '输入图层名称（如：医院）' })
  if (!name || !name.trim()) return
  const type = await showInputDialog({ title: '输入图层类型（point / line / polygon）', defaultValue: 'point' })
  if (!type || !['point', 'line', 'polygon'].includes(type.trim())) {
    showToast('图层类型仅支持 point / line / polygon')
    return
  }
  try {
    await api.addLayer(mapStore.currentMapId, {
      layer_type: type.trim(),
      name: name.trim(),
    })
    const resp = await api.getMap(mapStore.currentMapId)
    const data = resp.data || resp
    mapStore.setMapData(data)
    dispatchMapEvent('map-apply-data', { data })
    showToast('图层已添加')
  } catch (e: any) {
    showToast('添加图层失败: ' + e.message)
  }
}

async function removeSelectedLayer() {
  const layerId = selectedLayer.value
  if (!layerId || !mapStore.currentMapId) {
    showToast('请先选择图层')
    return
  }
  const known = mapStore.currentMapData?.layers?.some((l) => l.id === layerId)
  mapStore.removeLayer(layerId)
  selectedLayer.value = null
  if (known) {
    try {
      await api.removeLayer(mapStore.currentMapId, layerId)
    } catch {}
  }
  dispatchMapEvent('map-refresh-layers')
}

function moveLayer(dir: number) {
  const layerId = selectedLayer.value
  if (!layerId) {
    showToast('请先选择图层')
    return
  }
  if (dir < 0) mapStore.moveLayerUp(layerId)
  else mapStore.moveLayerDown(layerId)
  dispatchMapEvent('map-refresh-layers')
}

function openAttrTable() {
  if (!selectedLayer.value) {
    showToast('请先选择图层')
    return
  }
  appStore.openAttributeTable(selectedLayer.value)
}

function zoomToSelectedLayer() {
  if (!selectedLayer.value) {
    showToast('请先选择图层')
    return
  }
  dispatchMapEvent('map-zoom-to-layer', { layerId: selectedLayer.value })
}

function updateStyle(key: string, value: any) {
  if (!selectedLayer.value) return
  mapStore.updateLayerStyle(selectedLayer.value, { [key]: value })
  if (key === 'fillColor') styleFill.value = value
  if (key === 'color') styleColor.value = value
  if (key === 'weight') styleWeight.value = value
  if (key === 'opacity') styleOpacity.value = value
  dispatchMapEvent('map-refresh-layers')
}

function layerIconClass(type: string): string {
  if (type === 'polyline' || type === 'line') return 'line-icon'
  if (type === 'polygon' || type === 'area') return 'polygon-icon water-color'
  if (type === 'textLabel' || type === 'label') return 'point-icon label-color'
  return 'point-icon poi-color'
}

function openAnalysis(mode: 'buffer' | 'overlay' | 'nearest' | 'clip' | 'intersect' | 'union') {
  appStore.setAnalysisMode(mode)
}

function toggleFullscreen() {
  const el = document.querySelector('.qgis-editor')
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.().catch(() => showToast('无法全屏'))
  } else {
    document.exitFullscreen?.()
  }
}

function refreshMap() {
  dispatchMapEvent('map-refresh-layers')
  showToast('图层已刷新')
}

async function openExportMenu() {
  const fmt = await showInputDialog({ title: '选择导出格式：geojson / svg / png', defaultValue: 'png' })
  if (!fmt) return
  const format = fmt.trim().toLowerCase()
  if (!['geojson', 'svg', 'png'].includes(format)) {
    showToast('仅支持 geojson / svg / png')
    return
  }
  const mapId = mapStore.currentMapId
  if (!mapId) {
    showToast('请先生成地图')
    return
  }
  exportMapFile(mapId, format)
}

async function exportMapFile(mapId: string, format: string) {
  try {
    const resp: any = await api.exportMap(mapId, format)
    const data = resp.data || resp
    const ext = format === 'geojson' ? 'geojson' : format
    const filename = `map-${Date.now()}.${ext}`
    if (typeof data === 'string' && data.startsWith('data:image')) {
      const link = document.createElement('a')
      link.href = data
      link.download = filename
      link.click()
    } else {
      const mime = format === 'geojson' ? 'application/geo+json' : format === 'svg' ? 'image/svg+xml' : 'image/png'
      const blob = new Blob([String(data)], { type: mime })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    }
    showToast(`已导出 ${format.toUpperCase()}`)
  } catch (e: any) {
    showToast('导出失败: ' + e.message)
  }
}

function runDensityAnalysis() {
  dispatchMapEvent('map-density')
}

/** 图层类型 → GeoJSON 几何类型 */
function geomTypeToGeoJson(type: string): string {
  const t = (type || '').toLowerCase()
  if (['polygon', 'area'].includes(t)) return 'Polygon'
  if (['polyline', 'line', 'linestring'].includes(t)) return 'LineString'
  return 'Point'
}

/** 将图层坐标按目标投影转换并生成 GeoJSON */
function buildProjectedGeoJson(layer: any, targetEpsg: string): any {
  const fn = targetEpsg === '3857' ? lonLatToWebMercator : webMercatorToLonLat
  const gjType = geomTypeToGeoJson(layer?.type || '')
  const features: any[] = []
  if (Array.isArray(layer?.features) && layer.features.length > 0) {
    layer.features.forEach((f: any) => {
      features.push({
        type: 'Feature',
        properties: f?.properties || {},
        geometry: { type: gjType, coordinates: projectCoordsDeep(f?.coordinates, fn) },
      })
    })
  } else if (layer?.coordinates) {
    features.push({
      type: 'Feature',
      properties: {},
      geometry: { type: gjType, coordinates: projectCoordsDeep(layer.coordinates, fn) },
    })
  }
  return {
    type: 'FeatureCollection',
    crs: { type: 'name', properties: { name: `EPSG:${targetEpsg}` } },
    features,
  }
}

/** 触发浏览器下载 JSON 文件 */
function downloadJson(obj: any, filename: string) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/geo+json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 投影转换：将选中图层坐标从 WGS84 转换到目标投影并导出 GeoJSON */
async function runProjection() {
  const layer = selectedLayer.value ? mapStore.layerGroups[selectedLayer.value]?.data : null
  if (!layer) {
    showToast('请先在左侧图层面板选中要转换的图层')
    return
  }
  const input = await showInputDialog({ title: '目标坐标系 EPSG 代码（当前 WGS84 经纬度 4326，可转 3857）', defaultValue: '3857' })
  if (!input) return
  const epsg = input.trim().replace(/^epsg:/i, '')
  if (epsg === '4326') {
    showToast('当前已是 EPSG:4326 经纬度，无需转换')
    return
  }
  if (epsg !== '3857') {
    showToast('目前支持 4326 ↔ 3857（Web 墨卡托）')
    return
  }
  const geojson = buildProjectedGeoJson(layer, epsg)
  downloadJson(geojson, `${layer.name || '图层'}-EPSG${epsg}.geojson`)
  showToast(`已按 EPSG:${epsg} 转换并导出 GeoJSON`)
}

function formatAttrValue(value: any): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

watch(
  selectedLayer,
  (layerId) => {
    const layer = layerId ? mapStore.layerGroups[layerId]?.data : null
    const style = layer?.style || {}
    styleFill.value = style.fillColor || '#3b82f6'
    styleColor.value = style.color || '#1e40af'
    styleWeight.value = style.weight ?? 1
    styleOpacity.value = style.opacity ?? 1
  }
)

onMounted(() => {
  const el = document.getElementById('map-container')
  const handler = (e: Event) => {
    const denom = (e as CustomEvent).detail?.denominator
    if (denom) scale.value = denom
  }
  el?.addEventListener('map-scale-update', handler)
})

onUnmounted(() => {
  const el = document.getElementById('map-container')
  el?.removeEventListener('map-scale-update', () => {})
})
</script>

<style scoped>
.qgis-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f0f0;
  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: #2c2c2c;
}

/* 菜单栏 */
.qgis-menu-bar {
  height: 28px;
  background: #fafafa;
  border-bottom: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  padding: 0 4px;
  gap: 2px;
}

.menu-item {
  position: relative;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 3px;
  font-size: 12px;
}

.menu-item:hover {
  background: #e8e8e8;
}

.menu-label {
  user-select: none;
}

.menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: #fff;
  border: 1px solid #c0c0c0;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  padding: 4px 0;
  z-index: 1000;
  display: none;
}

.menu-item:hover .menu-dropdown {
  display: block;
}

.menu-bar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding-right: 8px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid #d0d0d0;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #0066cc;
  color: #fff;
  border-color: #0066cc;
}

.menu-item-child {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  white-space: nowrap;
}

.menu-item-child:hover {
  background: #0078d7;
  color: #fff;
}

.menu-item-child i {
  width: 16px;
  text-align: center;
  font-size: 12px;
}

.menu-separator {
  height: 1px;
  margin: 4px 8px;
  background: #e5e5e5;
  pointer-events: none;
}

.shortcut {
  margin-left: auto;
  color: #888;
  font-size: 11px;
}

.menu-item-child:hover .shortcut {
  color: rgba(255,255,255,0.8);
}

/* 工具栏 */
.qgis-toolbar {
  height: 36px;
  background: #f5f5f5;
  border-bottom: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  padding: 0 4px;
  gap: 4px;
}

.qgis-toolbar-second {
  height: 32px;
  background: #f0f0f0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0 4px;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: #d0d0d0;
  margin: 0 6px;
}

.toolbar-label {
  font-size: 11px;
  color: #666;
  padding: 0 4px;
  font-weight: 500;
}

.tool-btn {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #444;
  transition: all 0.15s;
}

.tool-btn:hover {
  background: #e4f0fb;
  border-color: #a8d5ff;
}

.tool-btn.active {
  background: #c4e0f9;
  border-color: #6cb6ff;
  color: #0066cc;
}

/* 自定义工具栏按钮 */
.toolbar-customize {
  position: relative;
}

.tool-customize-btn {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4) !important;
  color: white !important;
  border-color: transparent !important;
}

.tool-customize-btn:hover {
  background: linear-gradient(135deg, #0284c7, #0891b2) !important;
}

/* 工具组选择器 */
.tool-group-selector {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  width: 240px;
  background: white;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  overflow: hidden;
}

.selector-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.selector-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: #666;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.selector-list {
  max-height: 300px;
  overflow-y: auto;
  padding: 4px 0;
}

.selector-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 13px;
}

.selector-item:hover {
  background: #f0f9ff;
}

.selector-item i {
  color: #0ea5e9;
  font-size: 14px;
}

.selector-item .tool-count {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
}

.selector-footer {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.selector-btn {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #d0d0d0;
  background: white;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.selector-btn:hover {
  background: #f0f9ff;
  border-color: #0ea5e9;
}

.selector-btn.primary {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  color: white;
  border-color: transparent;
}

.selector-btn.primary:hover {
  background: linear-gradient(135deg, #0284c7, #0891b2);
}

/* 主体区域 */
.qgis-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左侧面板 */
.qgis-left-panel {
  width: 260px;
  background: #fff;
  border-right: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
}

.panel-tabs {
  display: flex;
  background: #f5f5f5;
  border-bottom: 1px solid #d0d0d0;
}

.panel-tab {
  flex: 1;
  padding: 8px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #666;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.panel-tab:hover {
  background: #e8e8e8;
}

.panel-tab.active {
  color: #0066cc;
  border-bottom-color: #0066cc;
  background: #fff;
}

.panel-tab i {
  font-size: 14px;
}

.panel-content {
  flex: 1;
  overflow: auto;
}

/* 图层面板 */
.panel-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  border-bottom: 1px solid #e8e8e8;
  background: #fafafa;
}

.panel-tool-btn {
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #555;
}

.panel-tool-btn:hover {
  background: #e4f0fb;
  border-color: #a8d5ff;
}

.panel-tool-separator {
  width: 1px;
  height: 16px;
  background: #d0d0d0;
  margin: 0 4px;
}

.layer-tree {
  padding: 4px 0;
}

.layer-empty {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 12px;
}

.layer-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.label-color {
  background: #7c3aed;
}

.layer-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 12px;
}

.layer-group-header:hover {
  background: #f0f7ff;
}

.group-icon {
  color: #f59e0b;
  font-size: 12px;
}

.group-count {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 0 6px;
  border-radius: 8px;
}

.layer-items {
  padding-left: 20px;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  cursor: pointer;
  font-size: 12px;
  border-left: 3px solid transparent;
}

.layer-item:hover {
  background: #f0f7ff;
}

.layer-item.selected {
  background: #e4f0fb;
  border-left-color: #0066cc;
}

.layer-icon {
  width: 18px;
  height: 14px;
  border-radius: 2px;
  flex-shrink: 0;
}

.point-icon {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.line-icon {
  height: 3px;
  background: #3b82f6;
  border-radius: 2px;
}

.polygon-icon {
  border: 1.5px solid #1e40af;
  background: rgba(59, 130, 246, 0.3);
}

.water-color {
  border-color: #1e40af;
  background: rgba(59, 130, 246, 0.5);
}

.building-color {
  border-color: #92400e;
  background: rgba(217, 119, 6, 0.5);
}

.poi-color {
  background: #dc2626;
}

.osm-icon {
  background: linear-gradient(135deg, #7eb87e 0%, #a8d8a8 100%);
}

.satellite-icon {
  background: linear-gradient(135deg, #4a5568 0%, #718096 100%);
}

/* 样式面板 */
.style-header {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.layer-name {
  font-size: 11px;
  color: #888;
  font-weight: normal;
}

.style-content {
  padding: 12px;
}

.style-section {
  margin-bottom: 16px;
}

.style-section label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: #555;
  font-weight: 500;
}

.style-select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
}

.color-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.color-input {
  width: 40px;
  height: 28px;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
}

.color-hex {
  font-size: 11px;
  color: #666;
  font-family: monospace;
}

.style-slider {
  width: 100%;
  margin: 4px 0;
}

.slider-value {
  font-size: 11px;
  color: #888;
}

/* 历史面板 */
.history-list {
  padding: 8px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  flex-shrink: 0;
}

.history-icon.add {
  background: #dcfce7;
  color: #16a34a;
}

.history-icon.style {
  background: #fef3c7;
  color: #d97706;
}

.history-icon.zoom {
  background: #dbeafe;
  color: #2563eb;
}

.history-info {
  flex: 1;
  min-width: 0;
}

.history-action {
  display: block;
  font-size: 12px;
  color: #333;
  margin-bottom: 2px;
}

.history-time {
  font-size: 11px;
  color: #999;
}

/* 地图画布 */
.qgis-map-canvas {
  flex: 1;
  position: relative;
  background: #fff;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-floating-tools {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 810;
}

.float-tool {
  width: 32px;
  height: 32px;
  border: 1px solid #d0d0d0;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #555;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.float-tool:hover {
  background: #f0f7ff;
  color: #0066cc;
}

/* 右侧面板 */
.qgis-right-panel {
  width: 280px;
  background: #fff;
  border-left: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
}

/* 处理工具箱 */
.toolbox-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e8e8;
}

.toolbox-search i {
  color: #999;
  font-size: 12px;
}

.toolbox-search input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 12px;
  background: transparent;
}

.toolbox-groups {
  padding: 4px 0;
}

.toolbox-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 500;
  font-size: 12px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.toolbox-group-header:hover {
  background: #f0f7ff;
}

.toolbox-items {
  padding: 4px 0;
}

.toolbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px 6px 32px;
  cursor: pointer;
  font-size: 12px;
  color: #444;
}

.toolbox-item:hover {
  background: #e4f0fb;
  color: #0066cc;
}

.toolbox-item i {
  font-size: 12px;
  width: 14px;
  text-align: center;
}

.toolbox-empty {
  padding: 20px 12px;
  text-align: center;
  color: #999;
  font-size: 12px;
}

/* 属性面板 */
.attr-header {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.feature-count {
  font-size: 11px;
  color: #888;
  font-weight: normal;
}

.attr-empty {
  padding: 40px 20px;
  text-align: center;
  color: #999;
}

.attr-empty i {
  font-size: 32px;
  margin-bottom: 12px;
  display: block;
  color: #ccc;
}

.attr-empty p {
  font-size: 12px;
}

.attr-content {
  padding: 8px 12px;
  overflow-y: auto;
  max-height: calc(100vh - 220px);
}

.attr-row {
  display: flex;
  align-items: flex-start;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 12px;
}

.attr-key {
  flex: 0 0 90px;
  color: #666;
  font-weight: 500;
  word-break: break-all;
}

.attr-value {
  flex: 1;
  color: #333;
  word-break: break-all;
}

/* 状态栏 */
.qgis-status-bar {
  height: 24px;
  background: #f0f0f0;
  border-top: 1px solid #d0d0d0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  font-size: 11px;
  color: #666;
}

.status-left,
.status-center,
.status-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-item .ok {
  color: #22c55e;
}

/* Toast */
.qgis-toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
