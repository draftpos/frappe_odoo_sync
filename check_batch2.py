import urllib.request, json, urllib.parse

url = 'http://127.0.0.1:8002/api/resource/Batch?limit_page_length=5&filters=' + urllib.parse.quote('[["item","=","SM003"]]')
req = urllib.request.Request(url, headers={
    'Authorization': 'token 8430883046ab2fb:a394dd475af983f',
    'Accept': 'application/json'
})
try:
    with urllib.request.urlopen(req, timeout=10) as res:
        print(res.read().decode()[:600])
except Exception as e:
    print(f'Error: {e}')
