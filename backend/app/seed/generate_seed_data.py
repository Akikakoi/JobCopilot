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

CITIES = ["上海", "北京", "深圳", "杭州", "广州", "成都", "远程", "不限"]

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


def _company_for(index: int) -> tuple[str, str]:
    return COMPANIES[index % len(COMPANIES)]


def write_jobs() -> int:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    for old in JOBS_DIR.glob("*.md"):
        old.unlink()

    for index, row in enumerate(JOB_ROWS, start=1):
        title, city_idx, smin, smax, emin, emax, required, preferred = row
        company, industry = _company_for(index)
        city = CITIES[city_idx]
        description = (
            f"负责「{title}」相关业务的设计、开发与迭代，与产品、设计、测试协作交付高质量功能；"
            f"持续优化系统性能与稳定性，参与技术方案评审。\n\n"
            f"我们希望你熟悉 {required.replace(',', '、')}，"
            f"有良好的工程习惯与沟通能力。"
        )
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
    return len(JOB_ROWS)


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
    return len(RESUME_NAMES)


if __name__ == "__main__":
    jobs = write_jobs()
    resumes = write_resumes()
    print(f"生成完成：{jobs} 个岗位 -> {JOBS_DIR}；{resumes} 份简历 -> {RESUMES_DIR}")
