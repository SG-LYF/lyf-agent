CATEGORY_TREE = {
    "01_公司业务": ["SG-LYF", "Shopee", "EasyBoss", "供应商", "合同"],
    "02_财务税务": ["银行", "发票", "IRAS", "付款凭证"],
    "03_政府与证件": ["MOM", "ACRA", "Corppass", "个人证件"],
    "04_家庭个人": ["教育", "旅行", "保险", "其他"],
    "05_图片与扫描件": [],
    "06_语音与会议记录": [],
    "07_学习资料": [],
    "99_待确认": [],
}

ALLOWED_CATEGORY_PATHS = []
for parent, children in CATEGORY_TREE.items():
    if children:
        for child in children:
            ALLOWED_CATEGORY_PATHS.append(f"{parent}/{child}")
    else:
        ALLOWED_CATEGORY_PATHS.append(parent)
