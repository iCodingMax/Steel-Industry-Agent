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

**重要规则（必须遵守）**：
1. 严格遵循 SKILL.md 中定义的执行流程和输出格式
2. 参考文档中的规则和标准应作为执行依据
3. 如果 SKILL.md 中定义了前置检查步骤（如数据完整性预检），必须优先执行。
   前置检查条件不满足时，按照 SKILL.md 中定义的对应输出模板输出，并停止后续流程。
4. SKILL.md 中定义的输出格式和章节结构必须完整输出，不得省略、跳过或提前停止。
   即使某章节因数据不足无法深入分析，也要明确标注"数据不足"并继续输出后续章节。
5. 直接输出执行结果，不要输出无关内容""")

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
            # ===== 1. 获取模型名 + 识别 context_length =====
            model_name = ""
            if llm_config:
                model_name = llm_config.get('model', '') or ''
            # 兜底：从全局 settings 中取 LLM 模型名（当 llm_config 未传 model 时）
            if not model_name:
                from app.core.config import settings as _cfg
                model_name = _cfg.XINFERENCE_LLM_MODEL or ''

            # 根据模型名自动识别 context_length（已知主流模型的上下文长度）
            # P2修复：必须与 Xinference 实际部署的 context_length 一致，否则会超出限制
            # 之前对 qwen3 给 131072 是错误的（实际 Xinference 部署 qwen3 通常为 40960）
            model_context_length = 65536  # 未识别模型默认 64k（原32k加倍）
            _mn = (model_name or '').lower()
            if any(k in _mn for k in ['qwen3', 'qwen2.5', 'qwen2']):
                # 注意：qwen3 官方支持 128k context，但 Xinference 部署时 max_model_len
                # 可能受 GPU 显存限制设为 40960。需根据实际部署调整。
                # 若 Xinference 重新部署时调大 max_model_len，这里同步调大。
                model_context_length = 40960   # 与 Xinference 实际部署一致
            elif any(k in _mn for k in ['glm4', 'glm-4', 'glm5', 'glm-5']):
                model_context_length = 131072
            elif 'glm' in _mn:
                model_context_length = 65536
            elif any(k in _mn for k in ['gemma4', 'gemma-4']):
                model_context_length = 131072
            elif 'gemma' in _mn:
                model_context_length = 65536
            elif 'deepseek' in _mn or 'gpt' in _mn:
                model_context_length = 131072
            logger.info(f"模型context_length识别: model={model_name}, context_length={model_context_length}")

            # ===== 2. 估算 prompt token 数（中文约1字符≈1.5 token）=====
            # Skill执行不传history给LLM，因此只估算prompt本身的token
            estimated_prompt_tokens = int(len(prompt) * 1.5)

            # ===== 3. 确定 Skill 专用的 max_tokens 目标值 =====
            # Skill 诊断报告（5章节）需要约 18000~30000 token 输出空间
            # 优先使用 env SKILL_MAX_TOKENS，应用级 max_tokens 作为 floor（更大则采用）
            from app.core.config import settings as _settings
            skill_desired_max_tokens = 32768
            if hasattr(_settings, 'SKILL_MAX_TOKENS') and _settings.SKILL_MAX_TOKENS:
                skill_desired_max_tokens = int(_settings.SKILL_MAX_TOKENS)
            # 应用级配置优先级最高（若用户在应用模型配置中显式设置更大max_tokens）
            if llm_config and llm_config.get('max_tokens'):
                app_set = int(llm_config['max_tokens'])
                if app_set >= 4096:
                    skill_desired_max_tokens = max(skill_desired_max_tokens, app_set)

            safety_margin = 1000  # 安全余量（原500加倍，避免上下文越界）

            # ===== 4. 在模型 context_length 内计算可用 max_tokens =====
            available_max_tokens = model_context_length - estimated_prompt_tokens - safety_margin
            if available_max_tokens < 2048:
                logger.error(
                    f"Prompt过长，无法在模型上下文限制内执行: "
                    f"prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens}, "
                    f"context={model_context_length}, available={available_max_tokens}"
                )
                result["answer"] = (
                    f"Skill执行失败：输入内容过长（约{estimated_prompt_tokens} token），"
                    f"已超出模型上下文可用空间（剩余{available_max_tokens} token）。"
                    f"请精简参考文档或输入数据后重新执行。"
                )
                result["success"] = False
                return result

            # 最终 max_tokens = min(desired, available)，不低于 2048
            final_max_tokens = max(2048, min(skill_desired_max_tokens, available_max_tokens))

            # 记录日志并写回配置
            prior_max = int(llm_config.get('max_tokens') or 0) if llm_config else 0
            if llm_config:
                llm_config = {**llm_config, 'max_tokens': final_max_tokens}
            else:
                llm_config = {'max_tokens': final_max_tokens}

            logger.info(
                f"Skill [{skill_name}] token预算: "
                f"prompt字符={len(prompt)}, 估算token={estimated_prompt_tokens}, "
                f"context={model_context_length}, desired={skill_desired_max_tokens}, "
                f"available={available_max_tokens}, "
                f"final_max_tokens={final_max_tokens} (原配置max_tokens={prior_max})"
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
                enable_short_output_detection=True,
            )

            # ===== 5. 检测截断并自动续写（最多续写2次） =====
            # 当答案末尾出现"输出已截断"提示时，识别为finish_reason=length
            # 自动调用LLM续写上一次输出。
            #
            # P2修复：原逻辑硬编码了"高炉炉况诊断"5个章节作为完整性校验标准，
            #         导致其他 Skill（如"产品营销文案"）输出不含这5章节时被误判为"缺失"，
            #         续写 prompt 又强制 LLM 输出炉况诊断章节，造成输出内容混淆。
            #         修复：5章节完整性校验 + 续写只对炉况诊断类 Skill 生效，
            #               其他 Skill 仅做基础过短检测（<500字符记录warning）。
            truncation_marker = "⚠️ **输出已截断**"
            is_furnace_diagnosis = (
                '炉况诊断' in (skill_name or '')
                or 'furnace' in (skill_name or '').lower()
                or 'diagnosis' in (skill_name or '').lower()
            )

            if is_furnace_diagnosis:
                # ---------- 仅炉况诊断类 Skill 启用 5 章节完整性续写 ----------
                #
                # P2修复：首次询问引导回复不应触发续写
                # Skill 首次执行时若 SKILL.md 定义了数据完整性预检步骤，
                # LLM 发现用户未提供数据，会输出"请您协助补充以下关键数据..."
                # 这种引导回复可能很长（如详细列出7个维度需要补充的数据），
                # 也可能列出5章节作为预告结构，但实质是数据征集而非诊断报告。
                # 续写只针对"用户已提供数据后的诊断报告不完整"场景。
                #
                # 检测条件（同时满足）：
                # 1. 回复不含全部5章节标题（不是完整诊断报告，可能为引导回复或不完整报告）
                #    注：即使引导回复列出5章节预告，只要不是诊断报告本身，
                #    通过条件2的数据征集类内容即可区分
                # 2. 回复包含数据征集类动词短语（请补充/请提供/请您告知...）
                # 3. 回复包含数据征集类名词（数据/信息/参数/指标/关键/以下/维度...）
                required_sections = [
                    "一、关键指标概览",
                    "二、分项诊断",
                    "三、综合判断",
                    "四、操作建议",
                    "五、诊断置信度",
                ]
                sections_count = sum(1 for s in required_sections if s in answer)
                has_all_sections = sections_count >= 5  # 完整诊断报告

                # 动词短语：扩充覆盖"请您"、"需要您"等更宽松的表达
                has_data_request_phrases = any(kw in answer for kw in [
                    '请补充', '请提供', '请协助', '请上传',
                    '请发送', '请提交', '请填写', '请输入',
                    '请告知', '请说明', '请描述', '请列出',
                    '请告诉我', '请按', '请您', '需要您',
                ])
                # 名词：扩充覆盖更多数据类名词
                has_data_request_objects = any(kw in answer for kw in [
                    '数据', '信息', '参数', '指标', '关键',
                    '以下', '维度', '字段', '数值', '数值表',
                    '原料', '燃料', '风温', '炉温', '铁水',
                    '焦比', '煤比', '透气性', '压差',
                ])
                is_data_request_reply = (
                    (not has_all_sections)
                    and has_data_request_phrases
                    and has_data_request_objects
                )
                if is_data_request_reply:
                    logger.info(
                        f"Skill [{skill_name}] 检测为数据预检引导回复"
                        f"（长度={len(answer)}字符，含{sections_count}/5章节标题，"
                        f"动词命中={has_data_request_phrases}，名词命中={has_data_request_objects}），"
                        f"跳过5章节续写逻辑"
                    )
                    result["answer"] = answer
                    logger.info(f"Skill [{skill_name}] 执行完成，回答长度={len(answer)}")
                    return result
                missing_required = [s for s in required_sections if s not in answer]
                is_truncated = truncation_marker in answer
                # 兜底：如果输出过短（<5000字符）且缺失2个以上章节，也视为需要续写
                too_short_missing_sections = len(answer) < 5000 and len(missing_required) >= 2

                if is_truncated or too_short_missing_sections:
                    # 先移除截断提示文本，再提取"最后完整章节"作为续写起点
                    base_answer = answer.split(truncation_marker)[0].rstrip()
                    trigger_reason = "截断标记" if is_truncated else f"输出过短({len(answer)}字符)且缺失章节"
                    logger.warning(
                        f"Skill [{skill_name}] 触发自动续写（原因={trigger_reason}），"
                        f"当前输出 {len(base_answer)} 字符，缺失章节: {missing_required}"
                    )
                    continuation_max = 2
                    for idx in range(1, continuation_max + 1):
                        # 剩余 token 预算：在原 final_max_tokens 基础上再分配一次续写空间
                        cont_tokens = min(final_max_tokens, available_max_tokens)
                        # 续写 prompt：把已输出内容最后3000字当上下文，要求LLM补全缺失章节
                        last_context = base_answer[-3000:] if len(base_answer) > 3000 else base_answer
                        cont_prompt = (
                            f"你正在续写《{skill_name}》的诊断报告（之前输出因长度限制或提前停止而不完整）。\n\n"
                            f"## 已输出内容的最后部分\n{last_context}\n\n"
                            f"## 报告章节完整性要求\n"
                            f"完整报告必须包含以下5个章节，缺失章节必须补全：\n"
                            f"一、关键指标概览\n"
                            f"二、分项诊断（含 2.1 送风制度 / 2.2 炉缸热状态 / 2.3 炉料运动 / 2.4 煤气分布 / 2.5 热负荷 / 2.6 原燃料评估）\n"
                            f"三、综合判断\n"
                            f"四、操作建议（立即执行 / 短期调整 / 中期优化）\n"
                            f"五、诊断置信度与数据缺口\n\n"
                            f"## 续写要求\n"
                            f"1. 只输出**缺失章节的内容**，不要重复任何已输出过的章节\n"
                            f"2. 章节标题使用与已输出一致的编号格式（三、四、五...）\n"
                            f"3. 每个判断必须解释“因为看到什么数据，所以判断是什么”\n"
                            f"4. 直接输出正文，不要有前言、总结或标记\n"
                            f"5. **必须完整输出所有缺失章节，不得提前停止**\n"
                            f"\n请开始续写："
                        )
                        cont_cfg = {**(llm_config or {}), 'max_tokens': cont_tokens}
                        logger.info(f"Skill续写第{idx}次: 上下文长度={len(cont_prompt)}, cont_tokens={cont_tokens}")
                        try:
                            cont_answer = await llm_service.chat(
                                prompt=cont_prompt,
                                system_prompt=None,
                                history=None,
                                config=cont_cfg,
                                enable_short_output_detection=True,
                            )
                        except Exception as _e:
                            logger.error(f"Skill续写第{idx}次异常: {type(_e).__name__}: {_e}")
                            break

                        # 去除续写结果中的截断提示
                        cont_answer_clean = cont_answer.split(truncation_marker)[0].rstrip()
                        base_answer = (base_answer.rstrip() + "\n\n" + cont_answer_clean.strip()).strip()
                        logger.info(
                            f"Skill续写第{idx}次完成: 续写{len(cont_answer_clean)}字符, "
                            f"当前总长度={len(base_answer)}"
                        )
                        # 如果续写结果不含截断标记，视为完整，停止
                        if truncation_marker not in cont_answer:
                            logger.info(f"Skill续写第{idx}次后无截断，视为完整")
                            break

                    # 最终检查：若仍缺失必需章节，在末尾显式提醒用户补问
                    missing_sections = [s for s in [
                        "三、综合判断", "四、操作建议", "五、诊断置信度",
                    ] if s not in base_answer]
                    if missing_sections:
                        base_answer += (
                            f"\n\n---\n\n"
                            f"⚠️ **诊断报告已自动续写2次但仍不完整**，缺失章节："
                            f"{', '.join(missing_sections)}。"
                            f"您可以继续提问：“请补充{missing_sections[0]}和后续章节”。"
                        )
                    else:
                        base_answer += "\n\n---\n\n✅ **因原始输出达到长度限制已自动续写，报告章节已补全**。"
                    answer = base_answer

                # 兜底续写：输出过短且缺失2章节时，强制要求LLM补全缺失章节
                final_missing = [s for s in required_sections if s not in answer]
                if len(answer) < 5000 and len(final_missing) >= 2:
                    logger.warning(
                        f"Skill [{skill_name}] 最终输出仍过短: {len(answer)} 字符, "
                        f"缺失章节: {final_missing}, 触发兜底强制续写"
                    )
                    try:
                        last_ctx = answer[-3000:] if len(answer) > 3000 else answer
                        final_prompt = (
                            f"你正在补全《{skill_name}》的诊断报告。当前报告仅输出了部分章节，"
                            f"必须补全以下缺失章节：{', '.join(final_missing)}\n\n"
                            f"## 已输出内容的最后部分\n{last_ctx}\n\n"
                            f"## 严格要求\n"
                            f"1. 必须输出所有缺失章节，不得遗漏\n"
                            f"2. 每个章节至少包含3-5个具体的分析判断\n"
                            f"3. 直接输出正文，不要有前言或标记\n"
                            f"4. 这是最后一次补全机会，必须完整输出\n"
                            f"\n请立即开始补全："
                        )
                        final_cfg = {**(llm_config or {}), 'max_tokens': min(final_max_tokens, available_max_tokens)}
                        final_answer = await llm_service.chat(
                            prompt=final_prompt,
                            system_prompt=None,
                            history=None,
                            config=final_cfg,
                            enable_short_output_detection=True,
                        )
                        final_clean = final_answer.split(truncation_marker)[0].rstrip()
                        answer = answer.rstrip() + "\n\n" + final_clean.strip()
                        logger.info(f"Skill兜底续写完成: 追加{len(final_clean)}字符, 总长度={len(answer)}")
                    except Exception as _e:
                        logger.error(f"Skill兜底续写异常: {type(_e).__name__}: {_e}")
                        answer += f"\n\n---\n\n⚠️ **诊断报告不完整**：系统尝试自动补全但失败，缺失章节：{', '.join(final_missing)}"
                elif len(answer) < 500:
                    logger.warning(
                        f"Skill [{skill_name}] 输出异常短: {len(answer)} 字符, "
                        f"可能是模型输出空间不足或提前停止"
                    )
            else:
                # ---------- 非炉况诊断类 Skill：仅做基础过短检测 ----------
                # 截断标记出现时也只追加通用提示，不强制续写特定章节
                if truncation_marker in answer:
                    base_answer = answer.split(truncation_marker)[0].rstrip()
                    logger.warning(
                        f"Skill [{skill_name}] 输出出现截断标记，但非炉况诊断类Skill，"
                        f"不强制续写特定章节。当前输出 {len(base_answer)} 字符"
                    )
                    answer = base_answer + "\n\n---\n\nℹ️ **输出已截断**：如需更详细内容，请继续提问以补充所需信息。"
                elif len(answer) < 500:
                    logger.warning(
                        f"Skill [{skill_name}] 输出异常短: {len(answer)} 字符, "
                        f"可能是模型输出空间不足或提前停止"
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
