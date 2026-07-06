from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


SEED_SOURCES = [
    "https://www.nyc.gov/",
    "https://www.nyc.gov/html/dot/html/home/home.shtml",
    "https://www.ny.gov/",
    "https://dmv.ny.gov/",
    "https://www.dfs.ny.gov/",
    "https://www.health.ny.gov/",
    "https://www.nyc.gov/site/buildings/index.page",
    "https://www.osha.gov/",
    "https://www.nyc.gov/site/nypd/index.page",
    "https://www.nycourts.gov/",
]

TOPIC_CATEGORY_LIBRARY = {
    "A.机动车交通事故类": [
        "车祸索赔",
        "交通事故",
        "网约车事故",
        "车辆保险理赔",
    ],
    "B.行人与骑行安全类": [
        "行人事故",
        "骑行事故",
        "外卖骑手事故",
        "校区周边交通安全",
    ],
    "C.公共交通安全类": [
        "地铁安全",
        "公交安全",
        "站台事故",
        "公共交通受伤",
    ],
    "D.无过错保险与理赔流程类": [
        "无过错保险",
        "保险理赔",
        "误工损失",
        "保险公司沟通",
    ],
    "E.责任认定与索赔常识类": [
        "责任认定",
        "比较过失",
        "证据保存",
        "索赔流程",
    ],
    "F.滑倒摔伤与天气风险类": [
        "滑倒摔伤",
        "黑冰",
        "雨雪天气出行安全",
        "冬季除雪责任",
    ],
    "G.商业场所安全类": [
        "商场安全",
        "超市安全",
        "餐厅安全",
        "电梯事故",
    ],
    "H.居住场所与房东责任类": [
        "公寓楼安全",
        "楼梯间安全",
        "租客安全",
        "房东责任",
    ],
    "I.工地事故与施工安全类": [
        "工地意外",
        "工地安全",
        "坠落事故",
        "施工区域行人安全",
    ],
    "J.医疗误诊与健康损害类": [
        "医院误诊",
        "急诊延误",
        "药物错误",
        "护理疏忽",
    ],
    "K.儿童、老人及弱势群体安全类": [
        "儿童受伤",
        "老人跌倒",
        "校车安全",
        "游乐场事故",
    ],
    "L.生活休闲与公共活动安全类": [
        "健身房受伤",
        "泳池安全",
        "节日公共安全",
        "宠物咬伤",
    ],
    "M.物业维护与公共设施类": [
        "人行道维护责任",
        "道路坑洞",
        "照明不足",
        "停车场地面缺陷",
    ],
    "N.华人生活场景专题类": [
        "法拉盛购物出行",
        "华人老人冬季出门安全",
        "华人家庭车祸后处理",
        "纽约租房安全",
    ],
}

TOPIC_EXPANSION_PATTERNS = {
    "车祸索赔": "纽约州车祸索赔与保险理赔要点",
    "交通事故": "纽约州交通事故后如何保留证据与处理索赔",
    "网约车事故": "纽约市网约车事故后责任如何判断",
    "车辆保险理赔": "纽约州车辆保险理赔常见问题",
    "行人事故": "纽约市行人过街受伤后如何处理",
    "骑行事故": "纽约市骑行事故后的责任与证据",
    "外卖骑手事故": "纽约市外卖骑手事故与道路安全",
    "校区周边交通安全": "纽约校区周边交通安全提醒",
    "地铁安全": "纽约地铁出行安全与受伤应对",
    "公交安全": "纽约公交乘车安全与受伤处理",
    "站台事故": "纽约站台事故后的证据保存",
    "公共交通受伤": "纽约公共交通受伤后怎么办",
    "无过错保险": "纽约州无过错保险申请流程",
    "保险理赔": "纽约州保险理赔材料准备指南",
    "误工损失": "纽约事故后误工损失如何准备材料",
    "保险公司沟通": "纽约事故后如何与保险公司沟通",
    "责任认定": "纽约事故责任认定常见误区",
    "比较过失": "纽约比较过失规则如何影响索赔",
    "证据保存": "纽约意外受伤后哪些证据要尽快保存",
    "索赔流程": "纽约人身伤害索赔流程简明科普",
    "滑倒摔伤": "纽约州滑倒摔伤与物业责任",
    "黑冰": "纽约冬季黑冰滑倒风险与责任问题",
    "雨雪天气出行安全": "纽约雨雪天气出行安全提醒",
    "冬季除雪责任": "纽约冬季除雪责任与滑倒受伤",
    "商场安全": "纽约商场公共区域安全与摔伤责任",
    "超市安全": "纽约超市滑倒受伤后的处理步骤",
    "餐厅安全": "纽约餐厅受伤后的责任判断",
    "电梯事故": "纽约电梯事故后的法律与安全问题",
    "公寓楼安全": "纽约公寓楼公共区域受伤责任",
    "楼梯间安全": "纽约公寓楼楼梯间受伤怎么办",
    "租客安全": "纽约租客常见居住安全问题",
    "房东责任": "纽约房东责任与租住安全",
    "工地意外": "纽约工地意外受伤的常见责任问题",
    "工地安全": "纽约工地安全事故科普",
    "坠落事故": "纽约坠落事故后的责任判断",
    "施工区域行人安全": "纽约施工区域行人安全提醒",
    "医院误诊": "纽约医院误诊后可以先做什么",
    "急诊延误": "纽约急诊延误带来的风险与记录重点",
    "药物错误": "纽约药物错误与患者自我保护",
    "护理疏忽": "纽约护理疏忽的常见信号",
    "儿童受伤": "纽约儿童公共场所受伤后的注意事项",
    "老人跌倒": "纽约老人跌倒后的安全与证据问题",
    "校车安全": "纽约校车安全与家长注意事项",
    "游乐场事故": "纽约游乐场事故后的应对建议",
    "健身房受伤": "纽约健身房受伤后的责任与证据",
    "泳池安全": "纽约泳池安全事故与风险防范",
    "节日公共安全": "纽约节日期间公共安全提醒",
    "宠物咬伤": "纽约宠物咬伤后的处理要点",
    "人行道维护责任": "纽约人行道维护责任与滑倒风险",
    "道路坑洞": "纽约道路坑洞导致受伤怎么办",
    "照明不足": "纽约照明不足导致受伤的责任问题",
    "停车场地面缺陷": "纽约停车场地面缺陷受伤责任",
    "法拉盛购物出行": "法拉盛购物出行安全与意外受伤提醒",
    "华人老人冬季出门安全": "纽约华人老人冬季出门安全提醒",
    "华人家庭车祸后处理": "纽约华人家庭车祸后处理步骤",
    "纽约租房安全": "纽约租房安全与常见责任问题",
}

MANUAL_TOPIC_URLS: dict[str, list[str]] = {
    "纽约州车辆保险理赔常见问题": [
        "https://dmv.ny.gov/insurance/insurance-requirements",
        "https://www.nyc.gov/site/dca/consumers/file-complaint.page",
        "https://www.nyc.gov/site/finance/vehicles/property-damage.page",
        "https://www.nycbar.org/get-legal-help/article/automobile-insurance/no-fault-basics/",
    ],
    "纽约州无过错保险申请流程": [
        "https://dmv.ny.gov/insurance/insurance-requirements",
        "https://www.nycbar.org/get-legal-help/article/automobile-insurance/no-fault-basics/",
        "https://www.nycollisionlawyer.com/new-york-no-fault-insurance-faq.html",
        "https://www.nycourts.gov/courthelp/AfterCourt/noFault.shtml",
    ],
    "纽约州保险理赔材料准备指南": [
        "https://dmv.ny.gov/insurance/insurance-requirements",
        "https://www.nyc.gov/site/dca/consumers/file-complaint.page",
        "https://www.nycbar.org/get-legal-help/article/automobile-insurance/no-fault-basics/",
        "https://www.dfs.ny.gov/consumers/help_for_homeowners/insurance_complaint",
    ],
    "纽约冬季黑冰滑倒风险与责任问题": [
        "https://www.nyc.gov/html/dot/html/infrastructure/sidewalkintro.shtml",
        "https://www.nyc.gov/site/buildings/safety/safety.page",
        "https://www.osha.gov/winter-weather",
        "https://www.weather.gov/safety/winter",
    ],
    "纽约州滑倒摔伤与物业责任": [
        "https://www.nyc.gov/html/dot/html/infrastructure/sidewalkintro.shtml",
        "https://www.nyc.gov/site/buildings/safety/safety.page",
        "https://www.osha.gov/slips-trips-falls",
        "https://www.nycbar.org/get-legal-help/article/personal-injury-and-accidents/premises-liability/",
    ],
    "纽约人行道维护责任与滑倒风险": [
        "https://www.nyc.gov/html/dot/html/infrastructure/sidewalkintro.shtml",
        "https://www.nyc.gov/site/hpd/services-and-information/tenants-rights-and-responsibilities.page",
        "https://www.nycbar.org/get-legal-help/article/personal-injury-and-accidents/premises-liability/",
        "https://www.nyc.gov/site/hpd/services-and-information/report-a-maintenance-issue.page",
        "https://portal.311.nyc.gov/article/?kanumber=KA-01074",
    ],
    "纽约施工区域行人安全提醒": [
        "https://www.nyc.gov/site/buildings/safety/safety.page",
        "https://www.osha.gov/construction",
        "https://www.nyc.gov/site/buildings/index.page",
        "https://www.nyc.gov/html/dot/html/pedestrians/safestreet.shtml",
    ],
    "纽约工地安全事故科普": [
        "https://www.osha.gov/construction",
        "https://www.nyc.gov/site/buildings/safety/safety.page",
        "https://www.nyc.gov/site/buildings/index.page",
        "https://www.osha.gov/fall-protection",
    ],
    "纽约公寓楼公共区域受伤责任": [
        "https://www.nyc.gov/site/hpd/services-and-information/tenants-rights-and-responsibilities.page",
        "https://www.nyc.gov/site/hpd/services-and-information/report-a-maintenance-issue.page",
        "https://portal.311.nyc.gov/article/?kanumber=KA-01074",
        "https://www.nycbar.org/get-legal-help/article/personal-injury-and-accidents/premises-liability/",
        "https://www.nyc.gov/html/dot/html/infrastructure/sidewalkintro.shtml",
    ],
}

BANNED_MARKETING_PHRASES = [
    "保证胜诉",
    "一定胜诉",
    "一定能赔",
    "一定可以获得赔偿",
    "一定拿到赔偿",
    "高额赔偿",
    "巨额赔偿",
    "高额赔偿不是问题",
    "只要受伤就能索赔",
    "保险公司一定会赔",
    "不请律师就一定吃亏",
    "百分百成功",
    "纽约第一",
    "最佳律师",
    "最强律师",
]

CAUTIOUS_REPLACEMENTS = {
    "保证胜诉": "是否能够获得支持，需要结合证据、事实和适用法律综合判断。",
    "一定胜诉": "案件结果需要结合证据和法律进行具体分析。",
    "一定能赔": "是否可以索赔以及赔偿范围，需要结合实际情况判断。",
    "一定可以获得赔偿": "能否获得赔偿，需要结合事实、证据和法律进行判断。",
    "一定拿到赔偿": "赔偿结果通常需要结合责任、伤情和保险情况综合评估。",
    "高额赔偿": "合理赔偿",
    "巨额赔偿": "相应赔偿",
    "高额赔偿不是问题": "赔偿范围需要根据案件情况具体分析。",
    "只要受伤就能索赔": "是否可以索赔，需要结合责任和证据判断。",
    "保险公司一定会赔": "保险理赔结果需要结合保单条款和事故情况判断。",
    "不请律师就一定吃亏": "是否需要律师协助，取决于案件复杂程度和个人情况。",
    "百分百成功": "具体结果需要个案分析。",
    "纽约第一": "纽约州执业团队",
    "最佳律师": "执业律师团队",
    "最强律师": "经验型律师团队",
}


@dataclass(slots=True)
class LLMSettings:
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    enable_query_generation: bool = True
    enable_source_filter: bool = True
    enable_blog_generation: bool = True
    enable_check_and_rewrite: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(slots=True)
class SearchSettings:
    mode: str = "no_api"
    max_results_per_query: int = 10
    max_articles_per_topic: int = 7
    min_articles_per_topic: int = 4
    enable_ddgs_search: bool = True
    enable_seed_source_search: bool = True
    enable_manual_urls: bool = True
    enforce_min_articles_per_topic: bool = False
    template_bootstrap_remote_enabled: bool = True
    template_bootstrap_remote_max_results_per_query: int = 6
    template_bootstrap_skip_remote_if_viable: bool = True
    request_timeout_seconds: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )


@dataclass(slots=True)
class GenerationSettings:
    target_article_word_count: int = 3200
    min_article_word_count: int = 2800
    max_article_word_count: int = 3600
    include_brand_message_probability: float = 0.6
    include_phone_cta_probability: float = 0.5
    phone_cta_text: str = "致电212-899-8888，获取免费咨询！"
    brand_message_title: str = "古灵王律师团寄语"
    brand_message_body: str = (
        "遇到意外受伤、保险沟通或责任判断问题时，越早保留信息，后续越容易把事情说清楚。"
    )


@dataclass(slots=True)
class CheckSettings:
    max_template_overall_similarity: float = 0.30
    max_template_paragraph_similarity: float = 0.60
    max_continuous_duplicate_chars: int = 30
    structure_style_pass_score: int = 75
    language_style_pass_score: int = 75


@dataclass(slots=True)
class LoggingSettings:
    level: str = "INFO"
    print_detailed_logs: bool = True
    save_logs: bool = True


@dataclass(slots=True)
class AppSettings:
    project_root: Path
    llm: LLMSettings = field(default_factory=LLMSettings)
    search: SearchSettings = field(default_factory=SearchSettings)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    check: CheckSettings = field(default_factory=CheckSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    seed_sources: list[str] = field(default_factory=lambda: list(SEED_SOURCES))
    manual_topic_urls: dict[str, list[str]] = field(
        default_factory=lambda: dict(MANUAL_TOPIC_URLS)
    )
    topic_category_library: dict[str, list[str]] = field(
        default_factory=lambda: dict(TOPIC_CATEGORY_LIBRARY)
    )
    topic_expansion_patterns: dict[str, str] = field(
        default_factory=lambda: dict(TOPIC_EXPANSION_PATTERNS)
    )
    banned_marketing_phrases: list[str] = field(
        default_factory=lambda: list(BANNED_MARKETING_PHRASES)
    )
    cautious_replacements: dict[str, str] = field(
        default_factory=lambda: dict(CAUTIOUS_REPLACEMENTS)
    )
    template_min_count: int = 4
    template_min_viable_count: int = 3
    template_bootstrap_seed_target: int = 4
