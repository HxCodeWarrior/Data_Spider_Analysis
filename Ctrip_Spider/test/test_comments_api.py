import requests
import json

def test_api_response(poi_id='76865'):
    """
    测试携程评论API返回的数据格式
    """
    post_url = "https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Content-Type': 'application/json',
        'Referer': 'https://m.ctrip.com/',
        'Origin': 'https://m.ctrip.com'
    }
    
    request_data = {
        "arg": {
            "channelType": 2,
            "collapseType": 0,
            "commentTagId": 0,
            "pageIndex": 1,
            "pageSize": 10,
            "poiId": poi_id,
            "sourceType": 1,
            "sortType": 3,
            "starType": 0
        },
        "head": {
            "cid": "09031069112760102754",
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
    
    try:
        response = requests.post(post_url, data=json.dumps(request_data), headers=headers, timeout=10)
        print(f"状态码: {response.status_code}")
        print("-" * 50)
        
        if response.status_code == 200:
            data = response.json()
            
            # 打印整体数据结构
            print("返回数据的主要键:")
            for key in data.keys():
                print(f"  - {key}")
            
            print("\n" + "="*50)
            
            # 如果有结果，打印第一条评论的详细信息
            if 'result' in data and 'items' in data['result'] and len(data['result']['items']) > 0:
                first_comment = data['result']['items'][0]
                print("第一条评论的完整结构:")
                print(json.dumps(first_comment, ensure_ascii=False, indent=2))
                
                print("\n" + "="*50)
                print("评论数量统计:")
                print(f"总评论数: {data['result'].get('totalCount', 'N/A')}")
                print(f"当前页评论数: {len(data['result']['items'])}")
            else:
                print("未找到评论数据")
        else:
            print(f"请求失败: {response.text[:200]}")
            
    except Exception as e:
        print(f"测试过程中出错: {e}")

if __name__ == "__main__":
    # 测试星海广场的API返回
    print("测试携程评论API返回格式...")
    test_api_response('76865')  # 星海广场