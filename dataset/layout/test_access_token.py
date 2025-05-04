import requests

def test_figma_token(access_token):
    headers = {
        'X-FIGMA-TOKEN': access_token  # 修正了 header 名称
    }
    
    url = "https://api.figma.com/v1/me"
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("\nToken is valid! ✅")
            return True
        else:
            print("\nToken is invalid! ❌")
            return False
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return False

# 使用你的 token
access_token = "figd_kxqLzF7HG2bXt5qcrvqT8BqGSUceHKTrlvavG61U"
test_figma_token(access_token)