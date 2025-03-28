# TODO: get images from aguvis原来的 layout component完整的合成的那些
# TODO: 对一个image，如何构建refusal数据 ?
# 先让模型对着图输出大量的instruction--有没有可能，直接用现有data？
# 然后把图去掉，给instruction挖空，让模型在无图情况下把这个instruction补全。
# 【问题:如何让模型输出 足够多 足够至 instruction?我们可能用上bbox吗】
# 【问题:有可能补至之后仍然是正确instruction?】
# 【问题:咱们对着什么图生instruction?】

def image_sample():
    """
    sample image from large datasets
    """
    pass

def main():
    pass

if __name__ == "__main__":
    main()