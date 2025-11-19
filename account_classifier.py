# -*- coding: utf-8 -*-
import os
import re
import json
import zipfile
from dataclasses import dataclass
from typing import List, Tuple, Optional, Iterable, Dict
import phonenumbers
from phonenumbers import geocoder

PHONE_REGEX = re.compile(r"(?:\+?\d{6,16})")

@dataclass
class AccountMeta:
    path: str            # 文件或目录绝对路径
    display_name: str    # 显示/打包用名称（保留原名）
    phone: Optional[str] # 形如 +8613xxxxxx（E.164）
    country_code: Optional[int]
    country_name_zh: Optional[str]

class AccountClassifier:
    """账号分类/打包工具：支持 tdata 和 session+json 两种来源"""

    def __init__(self) -> None:
        pass

    # -------------- 基础提取 --------------
    def _normalize_phone(self, raw: str) -> Optional[str]:
        """从字符串中提取并标准化为 E.164；失败返回 None"""
        if not raw:
            return None
        m = PHONE_REGEX.search(raw)
        if not m:
            return None
        cand = m.group(0)
        if not cand.startswith("+"):
            cand = "+" + cand
        try:
            num = phonenumbers.parse(cand, None)
            if phonenumbers.is_possible_number(num):
                return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            return None
        return None

    def _infer_phone_from_json(self, json_path: str) -> Optional[str]:
        """尝试在 JSON 文件中寻找手机号字段"""
        try:
            with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            # 常见字段
            for k in ("phone", "phone_number", "tel", "user_phone"):
                if isinstance(data.get(k), str):
                    p = self._normalize_phone(data[k])
                    if p:
                        return p
            # 常见嵌套
            user = data.get("user")
            if isinstance(user, dict):
                for k in ("phone", "phone_number"):
                    if isinstance(user.get(k), str):
                        p = self._normalize_phone(user[k])
                        if p:
                            return p
        except Exception:
            pass
        return None

    def _detect_country(self, phone: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
        """通过 phonenumbers 解析国家信息；失败返回 (None, None)"""
        if not phone:
            return None, None
        try:
            num = phonenumbers.parse(phone, None)
            code = num.country_code
            name = geocoder.country_name_for_number(num, "zh") or geocoder.country_name_for_number(num, "en")
            return code, (name or "未知")
        except Exception:
            return None, None

    # -------------- 元数据构造 --------------
    def build_meta_from_pairs(self, files: List[Tuple[str, str]], file_type: str) -> List[AccountMeta]:
        """
        将 FileProcessor.scan_zip_file 返回的列表 [(path, name)] 转为 AccountMeta 列表
        file_type: 'tdata' 或 'session'
        """
        metas: List[AccountMeta] = []
        for path, display_name in files:
            phone: Optional[str] = None

            # 1) 从名称里推断
            phone = self._normalize_phone(display_name)

            # 2) 目录/文件内查找 json 兜底
            if not phone:
                if os.path.isdir(path):
                    # tdata 目录下同级或下层可能会有描述 json
                    for root, _, fns in os.walk(path):
                        for fn in fns:
                            if fn.lower().endswith(".json"):
                                p = self._infer_phone_from_json(os.path.join(root, fn))
                                if p:
                                    phone = p
                                    break
                        if phone:
                            break
                else:
                    # session 同目录下可能有 .json
                    if path.lower().endswith(".json"):
                        phone = self._infer_phone_from_json(path)
                    else:
                        alt = path.replace(".session", ".json")
                        if os.path.exists(alt):
                            phone = self._infer_phone_from_json(alt)

            code, name = self._detect_country(phone)
            metas.append(AccountMeta(
                path=path,
                display_name=display_name,
                phone=phone,
                country_code=code,
                country_name_zh=name if name else None
            ))
        return metas

    # -------------- 命名与分组 --------------
    def country_key(self, m: AccountMeta) -> Tuple[str, str]:
        if m.country_code:
            return (m.country_name_zh or "未知"), str(m.country_code)
        return "未知", "000"

    def detect_bundle_country_label(self, metas: List[AccountMeta]) -> Tuple[str, str]:
        """用于按数量拆分时统一命名：若混合国家返回 ('混合','000')，全未知返回 ('未知','000')"""
        if not metas:
            return "未知", "000"
        codes: Dict[str, str] = {}  # code -> name
        code_list: List[str] = []
        for m in metas:
            name, code = self.country_key(m)
            codes[code] = name
            code_list.append(code)
        uniq = set(code_list)
        if len(uniq) == 1:
            code = next(iter(uniq))
            return codes.get(code, "未知"), code
        if uniq == {"000"}:
            return "未知", "000"
        return "混合", "000"

    # -------------- 打包 --------------
    def _zip_bundle(self, items: List[AccountMeta], out_dir: str, display_zip: str) -> str:
        """
        将传入的账号条目打成一个 zip 包
        修复点：
        - 保留 tdata 完整目录结构：手机号/tdata/Dxxxxxx/...
        - 对于 .session 同时打入同名 .json（同目录优先，找不到回退 sessions/）
        """
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, display_zip)

        written: set = set()  # 去重，避免重复写同一路径
        with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for it in items:
                # 账号根目录：优先用 E.164 手机号；没有则用显示名
                account_root = (it.phone or it.display_name or "").strip() or "account"

                if os.path.isdir(it.path):
                    base = it.path
                    base_is_tdata = os.path.basename(base).lower() == "tdata"

                    for rp, _, fns in os.walk(base):
                        for fn in fns:
                            full = os.path.join(rp, fn)
                            rel_from_base = os.path.relpath(full, base)
                            # 若源就是 tdata 目录，把 tdata 作为一级目录保留
                            if base_is_tdata:
                                arc_rel = os.path.join("tdata", rel_from_base)
                            else:
                                arc_rel = rel_from_base
                            arcname = os.path.join(account_root, arc_rel)
                            if arcname not in written:
                                zf.write(full, arcname=arcname)
                                written.add(arcname)
                else:
                    # 单文件：写入账号根目录
                    base_name = os.path.basename(it.path)
                    name_lower = base_name.lower()

                    arc_file = os.path.join(account_root, base_name)
                    if arc_file not in written:
                        zf.write(it.path, arcname=arc_file)
                        written.add(arc_file)

                    # 若是 .session，尝试附带同名 .json
                    if name_lower.endswith(".session"):
                        json_name = os.path.splitext(base_name)[0] + ".json"
                        json_candidates = [
                            os.path.join(os.path.dirname(it.path), json_name),
                            os.path.join(os.getcwd(), "sessions", json_name),
                        ]
                        for cand in json_candidates:
                            if os.path.exists(cand):
                                arc_json = os.path.join(account_root, json_name)
                                if arc_json not in written:
                                    zf.write(cand, arcname=arc_json)
                                    written.add(arc_json)
                                break
                    # 若是 .json，也尽量附带同名 .session（健壮性，防止只传了一个）
                    elif name_lower.endswith(".json"):
                        ses_name = os.path.splitext(base_name)[0] + ".session"
                        ses_candidates = [
                            os.path.join(os.path.dirname(it.path), ses_name),
                            os.path.join(os.getcwd(), "sessions", ses_name),
                        ]
                        for cand in ses_candidates:
                            if os.path.exists(cand):
                                arc_ses = os.path.join(account_root, ses_name)
                                if arc_ses not in written:
                                    zf.write(cand, arcname=arc_ses)
                                    written.add(arc_ses)
                                break
        return dst

    # -------------- 对外：按国家拆分 --------------
    def split_by_country(self, metas: List[AccountMeta], out_dir: str) -> List[Tuple[str, str, int]]:
        from collections import defaultdict
        groups: Dict[Tuple[str, str], List[AccountMeta]] = defaultdict(list)
        for m in metas:
            groups[self.country_key(m)].append(m)

        results: List[Tuple[str, str, int]] = []
        for (name, code), items in groups.items():
            qty = len(items)
            zip_name = f"{name}+{code}_{qty}.zip"
            path = self._zip_bundle(items, out_dir, zip_name)
            results.append((path, zip_name, qty))
        return results

    # -------------- 对外：按数量拆分 --------------
    def split_by_quantities(
        self,
        metas: List[AccountMeta],
        sizes: Iterable[int],
        out_dir: str,
        country_label: Optional[Tuple[str, str]] = None
    ) -> List[Tuple[str, str, int]]:
        """按给定 sizes 依次切分，命名 {国家}+{区号}+{数量}.zip，带序号后缀避免重名覆盖"""
        if country_label is None:
            country_label = self.detect_bundle_country_label(metas)
        name, code = country_label

        os.makedirs(out_dir, exist_ok=True)

        res: List[Tuple[str, str, int]] = []
        idx = 0
        metas_sorted = list(metas)
        total = len(metas_sorted)

        # 判断是否可能发生重名（同一国家/区号，数量重复）
        sizes_list = list(sizes)
        need_serial = sizes_list.count(1) > 1 or len(set(sizes_list)) != len(sizes_list)

        batch_no = 0
        for s in sizes_list:
            if idx >= total:
                break
            batch = metas_sorted[idx: idx + s]
            real = len(batch)
            if real == 0:
                break

            batch_no += 1
            base_name = f"{name}+{code}_{real}.zip"
            zip_name = base_name

            # 若需要保证唯一性，则追加批次序号
            if need_serial:
                zip_name = f"{name}+{code}_{real}--{batch_no}.zip"

            # 若仍存在重名（目录已有同名），继续自增后缀
            dedup_no = 1
            final_zip_name = zip_name
            while os.path.exists(os.path.join(out_dir, final_zip_name)):
                dedup_no += 1
                final_zip_name = f"{os.path.splitext(zip_name)[0]}--{dedup_no}.zip"

            path = self._zip_bundle(batch, out_dir, final_zip_name)
            res.append((path, final_zip_name, real))
            idx += s

        return res