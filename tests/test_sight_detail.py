def debug_response_structure(poi_id=87211):
    """
    探测API返回的数据结构
    """
    import json
    from requests import post
    
    # 使用与主类相同的请求数据
    request_data = {
        "poiId": poi_id,
        "scene": "basic",
        "head": {
            "cid": "09031065211914680477",
            "ctok": "",
            "cver": "1.0",
            "lang": "01",
            "sid": "8888",
            "syscode": "09",
            "auth": "",
            "xsid": "",
            "extension": []
        }
    }
    
    url = 'https://m.ctrip.com/restapi/soa2/18254/json/getPoiMoreDetail'
    
    try:
        response = post(url, json=request_data)
        response.raise_for_status()
        data = response.json()
        
        print("=== 完整的响应数据结构 ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        return data
        
    except Exception as e:
        print(f"请求失败: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    debug_response_structure(87211)