import secrets


# 32비트 int형 TOKEN 생성
def genToken():
    return secrets.randbits(32)
    
