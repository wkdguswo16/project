from random import randint
# hex형 TOKEN 생성
def gen_string(length:int):
    return "".join(hex(randint(0, 15))[2:] for i in range(length))
def gen_token():
    return randint(100000000,999999999)
def gen_uuid():
    return f"{gen_string(8)}-{gen_string(4)}-{gen_string(4)}-{gen_string(4)}-{gen_string(12)}"

if __name__ == "__main__":
    print(len(gen_uuid()))