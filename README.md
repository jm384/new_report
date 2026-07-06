# 纽约州华人律师事务所中文法律科普博客自动生成项目

项目按 `collect -> generate -> check` 的顺序运行，三阶段输出统一放在同一个主目录下：

`outputs/output_YYYYMMDD_HHMMSS/`

目录结构：
- `1_collect/`
- `2_generate/`
- `3_check/`

只有运行到对应阶段时，才会创建对应子目录。

运行示例：
```bash
python main.py --phase collect
python main.py --phase generate
python main.py --phase check
python main.py --phase all
```

单独运行 `generate` 或 `check` 时，可以指定历史主目录：

```bash
python main.py --phase generate --input-run-dir outputs/output_20260706_093329
python main.py --phase check --input-run-dir outputs/output_20260706_093329
```

输出说明：
- `1_collect/data/` 保存采集数据
- `1_collect/topic_research_docs/` 保存主题采集文档
- `2_generate/generated_blog_articles/` 保存初稿文章
- `3_check/quality_check_report.docx` 保存检查报告
- `3_check/final_articles/` 保存修复后的最终文章

模板目录要求：
- `template_docs/主题类别/多个模板文件`

注意：
- 文章输出使用 `docx`
- 检查报告只保留 `docx`
- 读取历史目录时兼容旧结构 `1_collect / 3_generate / 2_check`
