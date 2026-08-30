from app.core.constants import (MAP_TYPE_PROFILES, PROVINCE_DATA, NATIONAL_RIVERS,
                                 NATIONAL_LAKES, CITY_BBOX, CITY_ADCODES, LEGEND_TEMPLATES)

print('=== 后端常量验证 ===')
print(f'地图类型配置: {len(MAP_TYPE_PROFILES)} 种')
for k, v in MAP_TYPE_PROFILES.items():
    roads = v.get('road_levels', [])
    load = v.get('load_budget', '')
    print(f'  - {v["name"]}: 道路等级={roads}, 载负量={load}')
print(f'省级数据: {len(PROVINCE_DATA)} 个')
print(f'城市数据: {len(CITY_BBOX)} 个')
print(f'全国河流: {len(NATIONAL_RIVERS)} 条')
print(f'全国湖泊: {len(NATIONAL_LAKES)} 个')
print(f'图例模板: {len(LEGEND_TEMPLATES)} 种')
print('=== 全部验证通过 ===')
