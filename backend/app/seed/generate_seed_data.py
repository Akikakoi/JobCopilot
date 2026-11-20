"""生成种子数据（markdown）到仓库根目录 seed_data/。

运行：cd backend && .venv/Scripts/python.exe -m app.seed.generate_seed_data
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # JobCopilot/
JOBS_DIR = ROOT / "seed_data" / "jobs"
RESUMES_DIR = ROOT / "seed_data" / "resumes"

COMPANIES = [
    ("星澜科技", "互联网"),
    ("云枢智能", "人工智能"),
    ("拾光网络", "电子商务"),
    ("澜图数据", "大数据"),
    ("弦歌科技", "企业服务"),
    ("北辰云", "云计算"),
    ("木棉互动", "内容社区"),
    ("极衡信息", "金融科技"),
    ("白鹭软件", "SaaS"),
    ("远望数科", "数字营销"),
]

CITIES = ["上海", "北京", "深圳", "杭州", "广州", "成都", "远程", "不限", "苏州", "武汉", "南京", "西安"]

# (title, 城市序号, 薪资min, 薪资max, 经验min, 经验max, 必需技能, 加分技能)
JOB_ROWS = [
    ("Python 后端开发工程师", 0, 25, 35, 3, 5, "Python,FastAPI,MySQL,Redis", "Docker,Kubernetes,Celery"),
    ("高级后端工程师（Python）", 0, 30, 45, 5, 8, "Python,Django,MySQL,Redis", "微服务,Kafka"),
    ("Java 后端开发工程师", 1, 22, 32, 2, 5, "Java,Spring Boot,MySQL,Redis", "Dubbo,Kafka"),
    ("Go 后端工程师", 2, 25, 40, 3, 6, "Go,gRPC,MySQL,Redis", "Kubernetes,Prometheus"),
    ("后端开发工程师（交易方向）", 1, 28, 42, 3, 6, "Java,Spring Boot,MySQL,消息队列", "分库分表,Redis"),
    ("Python 数据服务工程师", 3, 20, 30, 2, 4, "Python,SQL,FastAPI", "Airflow,ClickHouse"),
    ("服务端开发工程师", 4, 18, 28, 1, 3, "Java,MySQL,Spring Boot", "Redis,Docker"),
    ("资深后端工程师（平台）", 0, 35, 50, 6, 10, "Java,分布式系统,MySQL,Redis", "Kubernetes,高并发"),
    ("Node.js 后端工程师", 6, 20, 32, 2, 5, "Node.js,TypeScript,MongoDB,Redis", "NestJS,GraphQL"),
    ("后端实习生", 0, 6, 9, 0, 1, "Python,SQL", "FastAPI,Git"),
    ("支付系统后端工程师", 2, 30, 45, 4, 7, "Java,MySQL,Redis,消息队列", "对账系统,高并发"),
    ("云原生后端工程师", 3, 28, 40, 3, 6, "Go,Kubernetes,Docker,Linux", "Istio,Prometheus"),
    ("前端开发工程师（React）", 0, 20, 30, 2, 4, "React,TypeScript,CSS,JavaScript", "Vite,Tailwind CSS"),
    ("高级前端工程师", 1, 28, 40, 4, 7, "React,TypeScript,组件设计,性能优化", "Next.js,微前端"),
    ("前端开发工程师（Vue）", 4, 16, 26, 1, 3, "Vue3,TypeScript,Vite,JavaScript", "Pinia,Element Plus"),
    ("H5 前端工程师", 2, 18, 28, 2, 4, "JavaScript,CSS,React,移动端适配", "小程序,Canvas"),
    ("前端架构师", 0, 35, 55, 6, 10, "React,TypeScript,前端工程化,微前端", "Node.js,性能优化"),
    ("Web 前端开发（数据可视化）", 3, 22, 34, 3, 5, "JavaScript,ECharts,React,CSS", "D3.js,Three.js"),
    ("小程序前端工程师", 6, 15, 24, 1, 3, "JavaScript,小程序,TypeScript", "Taro,React"),
    ("UI 前端开发工程师", 5, 14, 22, 1, 2, "HTML,CSS,JavaScript,Vue", "Figma,动效"),
    ("资深前端工程师（Node 方向）", 1, 30, 45, 5, 8, "TypeScript,Node.js,React,工程化", "NestJS,SSR"),
    ("前端性能优化专家", 7, 32, 48, 5, 8, "JavaScript,性能优化,浏览器原理", "WebGL,监控体系"),
    ("算法工程师（推荐系统）", 1, 35, 55, 3, 6, "Python,PyTorch,推荐算法,机器学习", "Spark,特征工程"),
    ("NLP 算法工程师", 0, 30, 50, 2, 5, "Python,Transformer,NLP,PyTorch", "LLM,微调"),
    ("大模型应用算法工程师", 0, 35, 60, 3, 6, "Python,LLM,RAG,LangChain", "Agent,向量数据库"),
    ("计算机视觉算法工程师", 2, 30, 45, 2, 5, "Python,PyTorch,目标检测,OpenCV", "ONNX,模型部署"),
    ("机器学习工程师", 3, 28, 42, 3, 6, "Python,机器学习,特征工程,SQL", "Spark,XGBoost"),
    ("数据挖掘工程师", 1, 25, 38, 2, 5, "Python,SQL,数据挖掘,统计学", "Hive,Hadoop"),
    ("算法实习生（大模型）", 0, 8, 12, 0, 1, "Python,PyTorch,深度学习", "LLM,Transformer"),
    ("搜索算法工程师", 4, 32, 48, 4, 7, "Python,搜索算法,排序模型,Elasticsearch", "Learning to Rank,NLP"),
    ("产品经理（B 端）", 0, 20, 32, 3, 6, "需求分析,产品设计,原型设计,B 端产品", "数据分析,SaaS"),
    ("产品经理（C 端）", 1, 18, 30, 2, 5, "用户研究,需求分析,原型设计,数据分析", "增长,社区产品"),
    ("高级产品经理（交易）", 2, 28, 42, 5, 8, "交易产品,需求分析,数据分析,项目管理", "电商,支付"),
    ("AI 产品经理", 0, 25, 40, 3, 6, "AI 产品,需求分析,LLM,数据分析", "Prompt,RAG"),
    ("产品经理（数据平台）", 3, 22, 35, 3, 6, "数据产品,SQL,需求分析,指标体系", "BI,数据治理"),
    ("产品运营（增长）", 1, 15, 25, 2, 4, "增长运营,数据分析,用户运营", "A/B 测试,活动策划"),
    ("B 端产品实习生", 0, 5, 8, 0, 1, "需求分析,产品设计", "Axure,数据分析"),
    ("项目经理（技术方向）", 4, 20, 30, 4, 7, "项目管理,敏捷开发,风险控制", "PMP,技术背景"),
    ("内容运营", 6, 10, 16, 1, 3, "内容运营,文案策划,数据分析", "短视频,社区"),
    ("用户运营", 1, 12, 20, 2, 4, "用户运营,数据分析,活动策划", "会员体系,社群"),
    ("数据运营分析师", 0, 16, 26, 2, 5, "SQL,数据分析,Excel,指标体系", "Python,Tableau"),
    ("商业化运营", 2, 18, 28, 3, 5, "商业化,数据分析,客户运营", "广告,投放"),
    ("新媒体运营", 6, 9, 15, 1, 3, "新媒体运营,文案策划,剪辑", "短视频,直播"),
    ("增长运营负责人", 1, 25, 35, 5, 8, "增长策略,用户增长,数据分析,团队管理", "私域,投放"),
    ("测试开发工程师", 0, 20, 30, 2, 5, "Python,自动化测试,Pytest,接口测试", "Selenium,CI/CD"),
    ("高级测试工程师", 2, 25, 35, 4, 7, "测试用例设计,自动化测试,性能测试", "JMeter,Python"),
    ("自动化测试工程师", 3, 18, 28, 2, 4, "Python,自动化测试,Selenium", "Pytest,Docker"),
    ("质量保障工程师（QA）", 4, 14, 22, 1, 3, "测试用例设计,缺陷管理,接口测试", "Postman,SQL"),
    ("测试实习生", 0, 5, 8, 0, 1, "测试用例设计,缺陷管理", "Python,Postman"),
    ("性能测试专家", 1, 28, 40, 5, 8, "性能测试,JMeter,性能调优,Linux", "压测平台,监控"),
]

RESUME_NAMES = [
    "张三", "李婷", "王浩然", "陈思远", "刘雨桐", "赵鹏", "孙悦", "周子墨",
    "吴佳怡", "郑凯", "冯雪", "何俊", "许静", "杨帆", "曹远", "邓琳",
    "韩磊", "沈梦", "钱多", "顾晓", "马骁", "朱琳", "胡杨", "林夕",
    "罗宇", "高远", "徐晴", "谢天", "唐糖", "于洋",
]

# (类型, 标题, 年限, 城市, 薪资min, 薪资max, 技能)
RESUME_TYPES = [
    ("完美匹配", "后端开发工程师", 3, "上海", 24, 35, "Python,FastAPI,MySQL,Redis,Docker"),
    ("完美匹配", "Java 后端工程师", 4, "北京", 26, 38, "Java,Spring Boot,MySQL,Redis,Kafka"),
    ("部分匹配", "Python 后端工程师", 3, "上海", 22, 32, "Python,Django,MySQL,Redis"),
    ("部分匹配", "前端开发工程师", 2, "上海", 18, 28, "React,JavaScript,CSS"),
    ("年限不足", "后端开发工程师", 1, "上海", 12, 18, "Python,MySQL,Redis"),
    ("年限不足", "前端开发工程师", 1, "北京", 12, 18, "React,TypeScript,CSS"),
    ("地域冲突", "Python 后端工程师", 3, "成都", 20, 30, "Python,FastAPI,MySQL,Redis"),
    ("地域冲突", "Java 后端工程师", 4, "广州", 22, 32, "Java,Spring Boot,MySQL,Redis"),
    ("薪资错位", "高级后端工程师", 5, "上海", 45, 60, "Python,Java,MySQL,Redis,微服务"),
    ("薪资错位", "前端工程师", 4, "北京", 40, 55, "React,TypeScript,性能优化"),
]

# ==================== 非 IT 行业扩展（岗位 + 简历） ====================
# (公司, 行业)
EXTRA_COMPANIES = [
    ("恒锐智造", "智能制造"),
    ("精工机械", "机械制造"),
    ("瑞衡银行", "银行"),
    ("安泰保险", "保险"),
    ("康宁医疗", "医疗健康"),
    ("仁和生物", "生物医药"),
    ("知行教育", "教育培训"),
    ("悦享零售", "零售"),
    ("每日鲜", "快消"),
    ("顺捷供应链", "物流供应链"),
    ("半山设计", "设计"),
    ("明德咨询", "财务与人力咨询"),
]

# (公司, 行业, 标题, 城市序号, 薪资min, 薪资max, 经验min, 经验max, 必需技能, 加分技能)
EXTRA_JOB_ROWS = [
    # 智能制造 / 机械
    ("恒锐智造", "智能制造", "机械设计工程师", 0, 15, 25, 3, 5, "机械设计,SolidWorks,AutoCAD,材料力学", "有限元分析,非标设计"),
    ("恒锐智造", "智能制造", "电气工程师", 8, 12, 20, 2, 5, "电气设计,PLC,自动控制,电气图纸", "西门子,伺服系统"),
    ("精工机械", "机械制造", "工艺工程师", 8, 10, 18, 3, 6, "工艺设计,机械加工,工装夹具", "精益生产,SPC"),
    ("精工机械", "机械制造", "质量工程师", 9, 9, 16, 2, 5, "质量管理,8D,质量体系", "IATF16949,审核"),
    ("精工机械", "机械制造", "生产计划专员", 8, 8, 14, 2, 4, "生产计划,物料计划,ERP", "排产,库存管理"),
    # 银行 / 保险
    ("瑞衡银行", "银行", "风控分析师", 0, 20, 35, 3, 6, "风险识别,SQL,数据分析,Excel建模", "Python,风控模型"),
    ("瑞衡银行", "银行", "理财经理", 10, 15, 25, 2, 5, "客户维护,理财规划,基金从业资格", "保险规划,高净值客户"),
    ("瑞衡银行", "银行", "信贷审批专员", 9, 12, 20, 2, 4, "信贷审核,财务分析,风险控制", "企业授信,尽职调查"),
    ("安泰保险", "保险", "保险核保专员", 11, 10, 18, 2, 5, "核保,保险产品,风险评估", "医学核保,理赔"),
    ("安泰保险", "保险", "合规专员", 0, 15, 25, 3, 5, "合规管理,监管政策,反洗钱", "法律职业资格,内控"),
    # 医疗健康
    ("康宁医疗", "医疗健康", "临床研究员", 0, 18, 30, 3, 6, "临床试验,GCP,医学统计", "CRO,方案撰写"),
    ("康宁医疗", "医疗健康", "医疗器械注册专员", 8, 12, 20, 2, 5, "医疗器械法规,注册申报,ISO13485", "FDA,CE认证"),
    ("仁和生物", "生物医药", "医药代表", 9, 10, 20, 1, 3, "学术推广,客户维护,医药知识", "医院资源,药品销售"),
    ("仁和生物", "生物医药", "医学编辑", 10, 10, 16, 2, 4, "医学写作,文献检索,英文", "SCI,临床数据"),
    ("康宁医疗", "医疗健康", "护士", 11, 8, 14, 2, 5, "护理操作,急救,患者沟通", "ICU,专科护理"),
    # 教育
    ("知行教育", "教育培训", "教研老师（数学）", 0, 12, 22, 3, 5, "数学教学,课程设计,教研", "竞赛,线上教学"),
    ("知行教育", "教育培训", "课程顾问", 9, 8, 15, 1, 3, "课程咨询,客户沟通,销售", "社群运营,续费"),
    ("知行教育", "教育培训", "教务管理", 10, 7, 12, 1, 3, "教务管理,排课,家校沟通", "数据分析,活动组织"),
    ("知行教育", "教育培训", "留学顾问", 0, 10, 20, 2, 5, "留学规划,英文,院校申请", "签证,文书"),
    # 零售 / 快消
    ("悦享零售", "零售", "门店店长", 0, 10, 18, 3, 5, "门店运营,团队管理,库存管理", "零售陈列,会员运营"),
    ("悦享零售", "零售", "商品采购专员", 8, 9, 16, 2, 4, "采购谈判,供应商管理,成本控制", "品类管理,快消"),
    ("每日鲜", "快消", "市场推广专员", 9, 8, 15, 1, 3, "活动策划,渠道推广,数据分析", "新媒体,异业合作"),
    ("每日鲜", "快消", "电商运营", 10, 10, 18, 2, 4, "店铺运营,数据分析,活动策划", "直播,内容运营"),
    # 物流 / 供应链
    ("顺捷供应链", "物流供应链", "供应链专员", 0, 10, 18, 2, 4, "供应链管理,采购,库存控制", "供应商开发,成本优化"),
    ("顺捷供应链", "物流供应链", "仓储主管", 8, 9, 15, 3, 5, "仓储管理,团队管理,WMS", "精益仓储,安全管理"),
    ("顺捷供应链", "物流供应链", "物流规划专员", 9, 10, 18, 2, 4, "物流规划,数据分析,成本优化", "路径优化,干线运输"),
    # 设计
    ("半山设计", "设计", "平面设计师", 0, 8, 15, 1, 3, "Photoshop,Illustrator,品牌设计", "排版,C4D"),
    ("半山设计", "设计", "室内设计师", 10, 10, 20, 2, 5, "AutoCAD,3DMAX,施工图", "软装,材料工艺"),
    ("半山设计", "设计", "品牌设计师", 0, 12, 22, 3, 5, "品牌视觉,VI设计,排版", "插画,动态设计"),
    # 财务 / 人力
    ("明德咨询", "财务与人力咨询", "会计", 9, 8, 14, 2, 5, "总账核算,报税,财务报表", "审计,成本会计"),
    ("明德咨询", "财务与人力咨询", "财务分析", 0, 15, 25, 3, 6, "财务分析,预算管理,Excel建模", "BI,经营分析"),
    ("明德咨询", "财务与人力咨询", "招聘专员", 10, 8, 15, 1, 3, "招聘渠道,面试,人才库", "校招,雇主品牌"),
    ("明德咨询", "财务与人力咨询", "薪酬绩效专员", 9, 10, 18, 2, 5, "薪酬核算,绩效考核,社保", "股权激励,劳动法"),
]

# (姓名, 简历类型, 目标职位, 年限, 城市, 薪资min, 薪资max, 技能, 公司)
EXTRA_RESUME_ROWS = [
    ("赵建国", "完美匹配", "机械设计工程师", 4, "上海", 18, 28, "机械设计,SolidWorks,AutoCAD,材料力学", "恒锐智造"),
    ("钱丽", "完美匹配", "电气工程师", 2, "苏州", 12, 18, "电气设计,PLC,自动控制", "恒锐智造"),
    ("孙浩然", "完美匹配", "风控分析师", 3, "上海", 20, 30, "风险识别,SQL,数据分析,Excel建模", "瑞衡银行"),
    ("李婉", "部分匹配", "理财经理", 3, "南京", 15, 22, "客户维护,理财规划", "瑞衡银行"),
    ("周敏", "年限不足", "临床研究员", 2, "上海", 16, 24, "临床试验,GCP,医学统计", "康宁医疗"),
    ("吴秀英", "完美匹配", "护士", 4, "西安", 9, 13, "护理操作,急救,患者沟通", "康宁医疗"),
    ("郑雅", "完美匹配", "教研老师（数学）", 5, "上海", 18, 25, "数学教学,课程设计,教研", "知行教育"),
    ("王强", "年限不足", "课程顾问", 1, "武汉", 8, 12, "课程咨询,销售", "知行教育"),
    ("冯丽丽", "完美匹配", "门店店长", 4, "上海", 12, 18, "门店运营,团队管理,库存管理", "悦享零售"),
    ("陈涛", "完美匹配", "供应链专员", 3, "上海", 12, 18, "供应链管理,采购,库存控制", "顺捷供应链"),
    ("褚静", "完美匹配", "平面设计师", 2, "上海", 9, 14, "Photoshop,Illustrator,品牌设计", "半山设计"),
    ("卫红", "完美匹配", "会计", 3, "武汉", 9, 13, "总账核算,报税,财务报表", "明德咨询"),
    ("蒋斌", "完美匹配", "财务分析", 4, "上海", 18, 25, "财务分析,预算管理,Excel建模", "明德咨询"),
    ("沈洁", "完美匹配", "招聘专员", 2, "南京", 9, 13, "招聘渠道,面试,人才库", "明德咨询"),
    ("韩雪", "地域冲突", "医学编辑", 3, "成都", 10, 15, "医学写作,文献检索,英文", "仁和生物"),
]


def _company_for(index: int) -> tuple[str, str]:
    return COMPANIES[index % len(COMPANIES)]


def _write_job(
    index: int,
    title: str,
    company: str,
    industry: str,
    city: str,
    smin: int,
    smax: int,
    emin: int,
    emax: int,
    required: str,
    preferred: str,
    description: str,
) -> None:
    content = f"""# {title}

- 公司: {company}
- 行业: {industry}
- 城市: {city}
- 薪资: {smin}-{smax}
- 经验: {emin}-{emax}
- 状态: open

## 必需技能
{required.replace(',', ', ')}

## 加分技能
{preferred.replace(',', ', ')}

## 岗位描述
{description}
"""
    (JOBS_DIR / f"job_{index:02d}.md").write_text(content, encoding="utf-8")


def write_jobs() -> int:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    for old in JOBS_DIR.glob("*.md"):
        old.unlink()

    total = 0
    for index, row in enumerate(JOB_ROWS, start=1):
        title, city_idx, smin, smax, emin, emax, required, preferred = row
        company, industry = _company_for(index)
        description = (
            f"负责「{title}」相关业务的设计、开发与迭代，与产品、设计、测试协作交付高质量功能；"
            f"持续优化系统性能与稳定性，参与技术方案评审。\n\n"
            f"我们希望你熟悉 {required.replace(',', '、')}，"
            f"有良好的工程习惯与沟通能力。"
        )
        _write_job(
            index, title, company, industry, CITIES[city_idx], smin, smax, emin, emax,
            required, preferred, description,
        )
        total = index

    for offset, row in enumerate(EXTRA_JOB_ROWS, start=1):
        company, industry, title, city_idx, smin, smax, emin, emax, required, preferred = row
        description = (
            f"负责「{title}」相关业务，与团队协作完成交付目标；持续优化流程与工作质量。\n\n"
            f"我们希望你具备 {required.replace(',', '、')} 相关经验，"
            f"沟通顺畅、责任心强。"
        )
        _write_job(
            total + offset, title, company, industry, CITIES[city_idx], smin, smax,
            emin, emax, required, preferred, description,
        )

    return total + len(EXTRA_JOB_ROWS)


def write_resumes() -> int:
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    for old in RESUMES_DIR.glob("*.md"):
        old.unlink()

    for index, name in enumerate(RESUME_NAMES):
        kind, title, years, city, smin, smax, skills = RESUME_TYPES[index % len(RESUME_TYPES)]
        school = ["复旦大学", "上海交通大学", "浙江大学", "北京邮电大学", "华中科技大学"][index % 5]
        company, _industry = COMPANIES[index % len(COMPANIES)]
        skill_list = [s.strip() for s in skills.split(",")]
        highlights = [
            f"负责核心模块开发，支撑日均 {10 + index} 万请求",
            "推动接口性能优化，P95 延迟下降 40%",
            "参与技术方案设计与代码评审",
        ]
        content = f"""# {name}

- 目标职位: {title}
- 工作年限: {years}
- 期望城市: {city}
- 期望薪资: {smin}-{smax}K
- 简历类型: {kind}

## 技能
{", ".join(skill_list)}

## 教育经历
- {school} | 本科 | 计算机科学与技术 | 2016-2020

## 工作经历
### {company} | {title} | 2020-2024
- {highlights[0]}
- {highlights[1]}
- {highlights[2]}

## 自我评价
踏实、有责任心，乐于学习新技术，重视工程质量与团队协作。
"""
        (RESUMES_DIR / f"resume_{index + 1:02d}.md").write_text(content, encoding="utf-8")

    base = len(RESUME_NAMES)
    schools = ["同济大学", "南京大学", "武汉大学", "西安交通大学", "四川大学"]
    for offset, row in enumerate(EXTRA_RESUME_ROWS, start=1):
        name, kind, title, years, city, smin, smax, skills, company = row
        school = schools[(offset - 1) % len(schools)]
        period = "2015-2019" if years >= 4 else "2017-2021"
        skill_list = [s.strip() for s in skills.split(",")]
        content = f"""# {name}

- 目标职位: {title}
- 工作年限: {years}
- 期望城市: {city}
- 期望薪资: {smin}-{smax}K
- 简历类型: {kind}

## 技能
{", ".join(skill_list)}

## 教育经历
- {school} | 本科 | 相关专业 | {period}

## 工作经历
### {company} | {title} | 2019-2024
- 负责{title}相关核心工作，持续优化流程与交付质量
- 与团队协作完成重点项目，获得业务方认可
- 参与流程改进与知识沉淀

## 自我评价
踏实、有责任心，沟通顺畅，重视结果与团队协作。
"""
        (RESUMES_DIR / f"resume_{base + offset:02d}.md").write_text(content, encoding="utf-8")
    return base + len(EXTRA_RESUME_ROWS)


if __name__ == "__main__":
    jobs = write_jobs()
    resumes = write_resumes()
    print(f"生成完成：{jobs} 个岗位 -> {JOBS_DIR}；{resumes} 份简历 -> {RESUMES_DIR}")
