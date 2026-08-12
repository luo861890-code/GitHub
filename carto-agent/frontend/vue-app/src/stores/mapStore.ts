import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import type { MapData, MapLayer, RouteData } from '@/types'

export const useMapStore = defineStore('map', () => {
  const currentMapData = ref<MapData | null>(null)
  const currentMapId = ref<string | null>(null)
  const currentTheme = ref('plain')
  const layerGroups = ref<Record<string, { visible: boolean; data: MapLayer }>>({})
  const routeData = ref<RouteData | null>(null)

  function setMapData(data: MapData) {
    currentMapData.value = data
    currentMapId.value = data.map_id || null
    if (data.theme) {
      currentTheme.value = data.theme
    }
    layerGroups.value = {}
    if (data.layers) {
      data.layers.forEach((layer) => {
        layerGroups.value[layer.id] = { visible: true, data: layer }
      })
    }
  }

  function clearAllLayers() {
    layerGroups.value = {}
    currentMapData.value = null
    currentMapId.value = null
    routeData.value = null
  }

  function setTheme(theme: string) {
    currentTheme.value = theme
  }

  function setRouteData(data: RouteData) {
    routeData.value = data
  }

  function clearRoute() {
    routeData.value = null
  }

  function toggleLayer(layerId: string, visible: boolean) {
    if (layerGroups.value[layerId]) {
      layerGroups.value[layerId].visible = visible
    }
  }

  return {
    currentMapData,
    currentMapId,
    currentTheme,
    layerGroups,
    routeData,
    setMapData,
    clearAllLayers,
    setTheme,
    setRouteData,
    clearRoute,
    toggleLayer,
  }
})
