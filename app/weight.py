from app.config  import AUTH_TOKEN

# ----- 加权轮询相关全局变量 Start---------
# 默认权重
WEIGHT_DEFAULT = 1
# TOKENS 数组
TOKENS = []
# TOKENS 初始权重数组
TOKEN_WEIGHTS = []
# 当前权重
CURRENT_WEIGHT = 0
# 当前权重索引
CURRENT_INDEX = -1
# TOKEN 总数
TOKENS_NUM = 0
# 最大权重
MAX_WEIGHT = 0
# 加权权重
GCD_WEIGHT = 0
# ----- 加权轮询相关全局变量 End---------


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def find_gcd_of_weights(weights):
    gcd_result = weights[0]
    for weight in weights[1:]:
        gcd_result = gcd(gcd_result, weight)
    return gcd_result


#  初始化 tokens 权重
def initialize_token_weights():
    global TOKEN_WEIGHTS, TOKENS_NUM, CURRENT_WEIGHT, TOKENS_WEIGHTS,MAX_WEIGHT,GCD_WEIGHT
    if not AUTH_TOKEN:
        raise ValueError("No tokens provided.")

    auth_tokens = AUTH_TOKEN.split(',')

    for auth_token in auth_tokens:
        token_parts = auth_token.split('---')
        token = token_parts[0].strip()
        weight = int(token_parts[1]) if len(token_parts) > 1 else WEIGHT_DEFAULT
        # 把 token 按顺序放入 tokens 数组中
        TOKENS.append(token)
        # 把 token 的权重按顺序放入 tokens_weights 中
        TOKEN_WEIGHTS.append(weight)

    # 获取最大权重
    MAX_WEIGHT = max(TOKEN_WEIGHTS)
    GCD_WEIGHT = find_gcd_of_weights(TOKEN_WEIGHTS)
    TOKENS_NUM = len(TOKENS)

# 初始化 tokens 权重
initialize_token_weights()
