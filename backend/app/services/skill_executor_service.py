"""
Skill 执行引擎

负责解析和执行上传的 Skill ZIP 包。
Skill 包结构（Claude Skills 格式）：
    skill-name/
        SKILL.md              ← Skill 定义（执行流程、参数体系、输出格式）
        scripts/              ← 可执行脚本（数据解析、报告生成）
        references/           ← 参考文档（诊断规则、故障模式等）
        assets/               ← 数据文件（输入模板、历史输出）
        reports/              ← 历史报告

执行策略：
1. 解压 ZIP 到临时目录
2. 读取 SKILL.md 获取 Skill 定义和执行流程
3. 读取 references/ 目录下的参考文档
4. 读取 assets/ 中的数据文件（输入模板、最新诊断数据）
5. 将 Skill 定义 + 参考文档 + 数据 组合为 prompt，调用 LLM 执行诊断分析
"""
import os
import json
import zipfile
import tempfile
from typing import List, Dict, Optional
from loguru import logger


class SkillExecutorService:
    """
    Skill 执行服务

    解析 Skill ZIP 包，提取专业知识文档和数据，
    组合为 LLM prompt 执行 Skill 定义的任务。
    """

    @staticmethod
    def extract_skill_zip(zip_path: str) -> Dict[str, str]:
        """
        解压 Skill ZIP 包，提取关键文件内容

        :param zip_path: ZIP 文件路径
        :return: 文件内容字典 {相对路径: 文件内容}
        """
        files_content: Dict[str, str] = {}

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue

                    # 只读取文本类文件（.md, .json, .txt, .py）
                    ext = os.path.splitext(info.filename)[1].lower()
                    if ext not in ('.md', '.json', '.txt', '.py'):
                        continue

                    try:
                        content = zf.read(info.filename).decode('utf-8')
                        files_content[info.filename] = content
                    except UnicodeDecodeError:
                        logger.debug(f"跳过无法解码的文件: {info.filename}")

        except zipfile.BadZipFile as e:
            logger.error(f"Skill ZIP文件损坏: {zip_path}, 错误={e}")
        except Exception as e:
            logger.error(f"解压Skill ZIP失败: {zip_path}, 错误={e}")

        return files_content

    @staticmethod
    def _parse_skill_files(files_content: Dict[str, str]) -> Dict[str, any]:
        """
        解析 Skill 包文件，分类提取关键内容

        :param files_content: 文件内容字典
        :return: 解析结果 {
            "skill_md": str,           # SKILL.md 内容
            "references": List[Dict],   # 参考文档列表
            "input_template": str,      # 输入模板
            "latest_data": str,         # 最新诊断数据
            "scripts": List[str],       # 脚本内容列表
        }
        """
        result = {
            "skill_md": "",
            "references": [],
            "input_template": "",
            "latest_data": "",
            "scripts": [],
        }

        for filepath, content in files_content.items():
            # 归一化路径分隔符
            norm_path = filepath.replace('\\', '/')

            # 1. SKILL.md — Skill 定义文件
            if norm_path.endswith('/SKILL.md') or norm_path.endswith('SKILL.md'):
                result["skill_md"] = content
                continue

            # 2. references/ 目录下的 .md 文件
            if '/references/' in norm_path and norm_path.endswith('.md'):
                doc_name = os.path.basename(norm_path).replace('.md', '')
                result["references"].append({
                    "name": doc_name,
                    "content": content
                })
                continue

            # 3. assets/input-template.json — 输入模板
            if 'input-template.json' in norm_path:
                result["input_template"] = content
                continue

            # 4. assets/diagnosis_output_latest.json — 最新诊断数据
            if 'diagnosis_output_latest.json' in norm_path:
                result["latest_data"] = content
                continue

            # 5. scripts/ 目录下的 .py 文件
            if '/scripts/' in norm_path and norm_path.endswith('.py'):
                script_name = os.path.basename(norm_path)
                result["scripts"].append(f"# 脚本: {script_name}\n{content}")
                continue

        return result

    @staticmethod
    def _build_skill_prompt(
        skill_md: str,
        references: List[Dict],
        input_template: str,
        latest_data: str,
        question: str,
        skill_name: str,
        skill_description: str,
    ) -> str:
        """
        构建 Skill 执行 prompt

        将 Skill 定义、参考文档、数据组合为完整的 LLM prompt。

        :param skill_md: SKILL.md 内容
        :param references: 参考文档列表
        :param input_template: 输入模板JSON
        :param latest_data: 最新诊断数据JSON
        :param question: 用户问题
        :param skill_name: Skill名称
        :param skill_description: Skill描述
        :return: 完整的 prompt
        """
        parts: List[str] = []

        # 1. 角色设定和 Skill 定义
        parts.append(f"""# Skill 执行任务

你正在执行 Skill: **{skill_name}**

## Skill 描述
{skill_description}

## Skill 定义 (SKILL.md)
{skill_md}
""")

        # 2. 参考文档
        if references:
            refs_text = []
            for ref in references:
                refs_text.append(f"### {ref['name']}\n{ref['content']}")
            parts.append(f"""## 参考文档 (references/)
以下是该 Skill 的专业知识参考文档，请严格遵循其中的规则和标准：

{chr(10).join(refs_text)}
""")
        else:
            parts.append("## 参考文档\n（Skill包中未包含参考文档）\n")

        # 3. 数据输入模板
        if input_template:
            parts.append(f"""## 数据输入模板 (input-template.json)
以下是该 Skill 的标准数据输入格式：

```json
{input_template}
```
""")

        # 4. 最新诊断数据（如果存在）
        if latest_data:
            parts.append(f"""## 最新诊断数据 (diagnosis_output_latest.json)
以下是从数据库获取的最新高炉运行数据，请基于此数据进行诊断分析：

```json
{latest_data}
```
""")

        # 5. 用户问题和执行指令
        parts.append(f"""## 用户问题
{question}

## 执行指令

请严格按照 SKILL.md 中定义的诊断流程执行 Skill，基于上述参考文档和数据完成以下任务：

1. **数据接收与校验**：检查最新诊断数据是否完整，标注缺失的关键参数
2. **建立基准参照**：根据参数指南确定各参数的基准范围
3. **逐层诊断分析**：按照"送风制度→炉缸热状态→炉料运动→煤气分布→热负荷→原燃料"的逻辑链条逐层分析
4. **综合判断**：给出炉况等级（五星制）和异常类型识别
5. **操作建议**：分"立即执行"、"短期调整"、"中期优化"三类给出建议
6. **诊断置信度**：标注数据缺口对诊断可靠性的影响

**重要规则**：
- 每个判断必须解释推理过程（"因为看到了XX数据，所以判断YY"）
- 量化优先：给具体数字，不说模糊词
- 安全第一：涉及严重异常时提醒"建议仅供参考，请结合现场实际情况决策"
- 如果数据不足以做出判断，明确告知用户需要补充哪些数据

请直接输出诊断报告，不要输出无关内容。""")

        return "\n\n".join(parts)

    @staticmethod
    async def execute_skill(
        zip_path: str,
        skill_name: str,
        skill_description: str,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, any]:
        """
        执行 Skill

        完整流程：
        1. 解压 ZIP 包，提取文件内容
        2. 解析分类文件（SKILL.md / references / assets）
        3. 构建 Skill 执行 prompt
        4. 调用 LLM 执行诊断分析

        :param zip_path: Skill ZIP 文件路径
        :param skill_name: Skill 名称
        :param skill_description: Skill 描述
        :param question: 用户问题
        :param history: 对话历史
        :return: 执行结果 {
            "answer": str,           # LLM 生成的诊断报告
            "skill_files": List[str], # 使用的文件列表
            "success": bool,
        }
        """
        result = {
            "answer": "",
            "skill_files": [],
            "success": True,
        }

        # 1. 检查 ZIP 文件是否存在（兼容相对路径和绝对路径）
        from app.services.tool_config_service import resolve_skill_path
        abs_zip_path = resolve_skill_path(zip_path)
        if not os.path.isfile(abs_zip_path):
            logger.error(f"Skill ZIP文件不存在: {zip_path} (解析后: {abs_zip_path})")
            result["answer"] = f"Skill文件不存在: {zip_path}"
            result["success"] = False
            return result

        # 2. 解压 ZIP，提取文件内容
        files_content = SkillExecutorService.extract_skill_zip(abs_zip_path)
        if not files_content:
            logger.error(f"Skill ZIP包为空或解压失败: {abs_zip_path}")
            result["answer"] = "Skill文件包为空或格式错误，无法执行。"
            result["success"] = False
            return result

        result["skill_files"] = list(files_content.keys())
        logger.info(f"Skill包解析完成: {len(files_content)} 个文件")

        # 3. 解析分类文件
        parsed = SkillExecutorService._parse_skill_files(files_content)

        if not parsed["skill_md"]:
            logger.warning(f"Skill包中未找到SKILL.md: {abs_zip_path}")
            # 没有 SKILL.md 也能继续，用 description 代替
            parsed["skill_md"] = f"Skill名称: {skill_name}\n描述: {skill_description}"

        logger.info(
            f"Skill解析: SKILL.md={'有' if parsed['skill_md'] else '无'}, "
            f"参考文档={len(parsed['references'])}个, "
            f"输入模板={'有' if parsed['input_template'] else '无'}, "
            f"最新数据={'有' if parsed['latest_data'] else '无'}, "
            f"脚本={len(parsed['scripts'])}个"
        )

        # 4. 构建 Skill 执行 prompt
        prompt = SkillExecutorService._build_skill_prompt(
            skill_md=parsed["skill_md"],
            references=parsed["references"],
            input_template=parsed["input_template"],
            latest_data=parsed["latest_data"],
            question=question,
            skill_name=skill_name,
            skill_description=skill_description,
        )

        # 5. 调用 LLM 执行诊断
        from app.services.llm_service import llm_service

        try:
            logger.info(f"开始执行Skill [{skill_name}]，prompt长度={len(prompt)}")

            answer = await llm_service.chat(
                prompt=prompt,
                system_prompt=None,
                history=history,
            )

            result["answer"] = answer
            logger.info(f"Skill [{skill_name}] 执行完成，回答长度={len(answer)}")

        except Exception as e:
            logger.error(f"Skill执行异常: {skill_name}, 错误={e}", exc_info=True)
            result["answer"] = f"Skill执行过程中出现错误：{str(e)}"
            result["success"] = False

        return result


# 服务实例
skill_executor_service = SkillExecutorService()
logger.info("Skill执行服务实例已创建")
