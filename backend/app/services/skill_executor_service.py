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
import re
import json
import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

# 项目根目录（backend/ 的上级目录）
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)


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
        max_prompt_chars: int = 14000,
    ) -> str:
        """
        构建 Skill 执行 prompt

        将 Skill 定义、参考文档、数据组合为完整的 LLM prompt。
        为避免超出模型上下文长度限制（qwen3 context_length=40960 token），
        对参考文档进行智能截断，确保总 prompt 在安全范围内。

        :param skill_md: SKILL.md 内容
        :param references: 参考文档列表
        :param input_template: 输入模板JSON
        :param latest_data: 最新数据JSON
        :param question: 用户问题
        :param skill_name: Skill名称
        :param skill_description: Skill描述
        :param max_prompt_chars: prompt最大字符数（默认14000，约21000 token，为max_tokens留出充足空间）
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

        # 2. 参考文档（根据剩余可用空间智能截断）
        if references:
            # 先计算不含参考文档的 prompt 长度（框架+SKILL.md+指令+问题等）
            frame_size = sum(len(p) for p in parts) + len(question) + 800  # 800为指令和框架的预估长度
            remaining = max_prompt_chars - frame_size
            # 每个参考文档分配的字符数
            per_ref_limit = max(1000, remaining // len(references)) if remaining > 1000 else 1000

            refs_text = []
            for ref in references:
                content = ref['content']
                if len(content) > per_ref_limit:
                    content = content[:per_ref_limit] + "\n\n... (文档已截断，仅展示前部分内容)"
                    logger.debug(f"参考文档[{ref['name']}]已截断: {len(ref['content'])} -> {per_ref_limit} 字符")
                refs_text.append(f"### {ref['name']}\n{content}")
            parts.append(f"""## 参考文档 (references/)
以下是该 Skill 的专业知识参考文档，请参考其中的规则和标准：

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

        # 4. 最新数据（如果存在）
        if latest_data:
            parts.append(f"""## 最新数据 (diagnosis_output_latest.json)
以下是从数据库获取的最新数据，请基于此数据进行分析：

```json
{latest_data}
```
""")

        # 5. 用户问题和执行指令（通用指令，适用于所有 Skill 类型）
        parts.append(f"""## 用户问题
{question}

## 执行指令

请严格按照 SKILL.md 中定义的流程执行 Skill，基于上述参考文档和数据完成用户要求的任务。

**重要规则**：
- 严格遵循 SKILL.md 中定义的执行流程和输出格式
- 参考文档中的规则和标准应作为执行依据
- 如果数据不足以完成任务，明确告知用户需要补充哪些信息
- 直接输出执行结果，不要输出无关内容""")

        return "\n\n".join(parts)

    @staticmethod
    async def execute_skill(
        zip_path: str,
        skill_name: str,
        skill_description: str,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        llm_config: Optional[Dict[str, any]] = None,
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
        :param llm_config: 应用级LLM配置（base_url, api_key, model 等），覆盖默认配置
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

        # 如果文件不存在，尝试在 uploads/skills/ 目录中按 skill 名称搜索匹配的文件
        # 此情况通常由数据库中存储的旧路径指向已被删除/覆盖的文件导致
        if not os.path.isfile(abs_zip_path):
            match = re.search(r'skill_\d+_(.+)\.zip', zip_path)
            if match:
                skill_name = match.group(1)
                skills_dir = os.path.join(_PROJECT_ROOT, 'uploads', 'skills')
                if os.path.isdir(skills_dir):
                    for fname in os.listdir(skills_dir):
                        if skill_name in fname and fname.endswith('.zip'):
                            abs_zip_path = os.path.join(skills_dir, fname)
                            logger.info(f"自动匹配到Skill文件: {abs_zip_path} (原路径: {zip_path})")
                            break

        if not os.path.isfile(abs_zip_path):
            logger.error(f"Skill ZIP文件不存在: {zip_path} (解析后: {abs_zip_path})")
            result["answer"] = "Skill文件不存在，请重新上传Skill文件。"
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
        try:
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
        except Exception as e:
            logger.error(f"Skill文件解析异常: {skill_name}, {type(e).__name__}: {e}", exc_info=True)
            result["answer"] = f"Skill文件解析失败：{type(e).__name__}: {str(e)}"
            result["success"] = False
            return result

        # 4. 构建 Skill 执行 prompt
        try:
            prompt = SkillExecutorService._build_skill_prompt(
                skill_md=parsed["skill_md"],
                references=parsed["references"],
                input_template=parsed["input_template"],
                latest_data=parsed["latest_data"],
                question=question,
                skill_name=skill_name,
                skill_description=skill_description,
            )
        except Exception as e:
            logger.error(f"Skill prompt构建异常: {skill_name}, {type(e).__name__}: {e}", exc_info=True)
            result["answer"] = f"Skill prompt构建失败：{type(e).__name__}: {str(e)}"
            result["success"] = False
            return result

        # 5. 调用 LLM 执行
        from app.services.llm_service import llm_service

        try:
            # 获取模型名，用于确定 context_length
            model_name = ""
            if llm_config:
                model_name = llm_config.get('model', '') or ''

            # 根据模型名自动识别 context_length（已知主流模型的上下文长度）
            # 未识别的模型默认 32768 token
            model_context_length = 32768
            if 'qwen3' in model_name.lower():
                model_context_length = 40960
            elif 'qwen2.5' in model_name.lower() or 'qwen2' in model_name.lower():
                model_context_length = 32768
            elif 'gemma4' in model_name.lower():
                model_context_length = 32768
            elif 'gemma' in model_name.lower():
                model_context_length = 32768
            elif 'glm' in model_name.lower():
                model_context_length = 32768
            elif 'deepseek' in model_name.lower():
                model_context_length = 128000
            elif 'gpt' in model_name.lower():
                model_context_length = 128000
            logger.info(f"模型context_length识别: model={model_name}, context_length={model_context_length}")

            # 估算 prompt token 数（中文约1字符≈1.5 token）
            # 注意：Skill执行不传history给LLM，因此只估算prompt本身的token
            estimated_prompt_tokens = int(len(prompt) * 1.5)

            safety_margin = 500  # 安全余量

            # 自动调整 max_tokens，确保 prompt_tokens + max_tokens <= context_length
            available_max_tokens = model_context_length - estimated_prompt_tokens - safety_margin

            # 获取原始 max_tokens
            if llm_config:
                original_max_tokens = llm_config.get('max_tokens') or 20480
            else:
                original_max_tokens = 20480

            if available_max_tokens < original_max_tokens:
                if available_max_tokens < 1024:
                    # prompt 太长，即使 max_tokens 设为最小也无法容纳
                    logger.error(
                        f"Prompt过长，无法在模型上下文限制内执行: "
                        f"prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens}, "
                        f"模型context_length={model_context_length}"
                    )
                    result["answer"] = (
                        f"Skill执行失败：Prompt内容过长（{len(prompt)}字符，约{estimated_prompt_tokens} token），"
                        f"超过了模型的上下文长度限制（{model_context_length} token）。"
                        f"请精简Skill包中的参考文档或缩短问题。"
                    )
                    result["success"] = False
                    return result

                # 调整 max_tokens 以适应上下文限制
                adjusted_max_tokens = available_max_tokens
                if llm_config:
                    llm_config = {**llm_config, 'max_tokens': adjusted_max_tokens}
                else:
                    llm_config = {'max_tokens': adjusted_max_tokens}
                logger.warning(
                    f"Prompt较长，自动调整max_tokens: {original_max_tokens} -> {adjusted_max_tokens} "
                    f"(prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens})"
                )
            else:
                # 上下文空间充足，向上调整 max_tokens 到合理值
                # 确保输出空间至少 8192 token，上限 16384 token
                target_max = min(available_max_tokens, 16384)
                if target_max > original_max_tokens:
                    if llm_config:
                        llm_config = {**llm_config, 'max_tokens': target_max}
                    else:
                        llm_config = {'max_tokens': target_max}
                    logger.info(
                        f"上下文充足，向上调整max_tokens: {original_max_tokens} -> {target_max} "
                        f"(available={available_max_tokens}, prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens})"
                    )
                else:
                    logger.info(
                        f"max_tokens无需调整: original={original_max_tokens}, available={available_max_tokens} "
                        f"(prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens})"
                    )

            logger.info(
                f"开始执行Skill [{skill_name}]，prompt长度={len(prompt)}, "
                f"估算token={estimated_prompt_tokens}, max_tokens="
                f"{llm_config.get('max_tokens', original_max_tokens) if llm_config else original_max_tokens}"
            )

            # Skill执行不传history给LLM：
            # 1. Skill prompt已包含所有必要信息（定义/参考文档/数据/问题）
            # 2. 对话历史会占用大量上下文，导致max_tokens不足
            # 3. 多轮交互上下文已在路由层处理（router_service的上下文保持逻辑）
            answer = await llm_service.chat(
                prompt=prompt,
                system_prompt=None,
                history=None,
                config=llm_config,
            )

            result["answer"] = answer
            logger.info(f"Skill [{skill_name}] 执行完成，回答长度={len(answer)}")

        except Exception as e:
            logger.error(f"Skill执行异常: {skill_name}, {type(e).__name__}: {e}", exc_info=True)
            result["answer"] = f"Skill执行过程中出现错误：{type(e).__name__}: {str(e)}"
            result["success"] = False

        return result


# 服务实例
skill_executor_service = SkillExecutorService()
logger.info("Skill执行服务实例已创建")
