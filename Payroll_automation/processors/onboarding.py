"""
ONBOARDING
Candidate e-mails documents -> the tool opens the mail, downloads each attachment (Word files),
reads them, checks completeness / identity / validity / experience / background, and answers the candidate.
Systems: Mail server, HRIS (background check), Document store (decision memo).
"""
import base64
import re
from datetime import date
from core.common import Result, run_date
from core.docparse import field, read_text
from processors.base import notify, archive_memo

LABEL = {"resume": "履歴書", "career_history": "職務経歴書", "graduation_certificate": "卒業（見込）証明書",
         "id_copy": "本人確認書類", "offer_acceptance": "内定承諾書", "signed_contract": "雇用契約書（署名済）",
         "bank_form": "給与振込口座届", "health_certificate": "健康診断書", "withholding_slip": "源泉徴収票",
         "dependent_form": "扶養控除等申告書", "residence_certificate": "住民票"}


def norm(s):
    return re.sub(r"\s+", "", s or "")


def process(row, api, cfg, ctx):
    ob, today, case, ht = cfg["onboarding"], run_date(cfg), row["case_id"], row["hire_type"]
    inbox = api.get("/mail/inbox", case_ref=case, folder="inbox", kind="application")
    if not inbox:
        return Result("NEEDS_REVIEW", "受信箱に該当の応募メールが見つかりません（要確認）", codes=["mail_not_found"])
    mail = api.get(f"/mail/{inbox[0]['id']}")
    applicant = mail["from_name"]

    docs = {}
    for a in mail["attachments"]:
        att = api.get(f"/mail/{mail['id']}/attachments/{a['doc_type']}")
        docs[a["doc_type"]] = read_text(att["filename"], base64.b64decode(att["content_b64"]))

    fixable, fatal = [], []
    for d in ob["required_documents"][ht]:
        if d not in docs:
            fixable.append(("missing_document", f"提出書類不足: {LABEL[d]}"))
    for d, text in docs.items():
        n = field(text, "氏名")
        if n and norm(n) != norm(applicant):
            fixable.append(("name_mismatch", f"氏名不一致: {LABEL[d]}（{n}）"))
    for d, text in docs.items():
        issued = field(text, "発行日")
        if issued:
            age = (today - date.fromisoformat(issued)).days
            if age > ob["certificate_max_age_days"]:
                fixable.append(("certificate_old", f"{LABEL[d]}の発行日が古い（{age}日前／有効{ob['certificate_max_age_days']}日以内）"))
    for d in ("signed_contract", "offer_acceptance"):
        if d in docs and field(docs[d], "署名") != "済":
            fixable.append(("unsigned", f"{LABEL[d]}に署名がありません"))
    if "id_copy" in docs:
        birth, exp = field(docs["id_copy"], "生年月日"), field(docs["id_copy"], "有効期限")
        if birth and (today - date.fromisoformat(birth)).days < ob["min_age"] * 365.25:
            fatal.append(("under_age", f"年齢要件を満たしていません（{ob['min_age']}歳以上）"))
        if exp and date.fromisoformat(exp) < today:
            fixable.append(("id_expired", "本人確認書類の有効期限切れ"))
    src = docs.get("career_history") or docs.get("resume") or ""
    exp_txt = field(src, "経験年数")
    exp_years = float(re.sub(r"[^\d.]", "", exp_txt)) if exp_txt else 0.0
    need = ob["min_experience_years"][ht]
    if exp_years < need:
        fatal.append(("experience", f"経験年数不足（必要{need}年／実績{exp_years}年）"))
    if ht == "契約社員" and "signed_contract" in docs and not field(docs["signed_contract"], "契約期間"):
        fixable.append(("contract_period", "契約期間の記載がありません"))
    bg = api.get(f"/hr/background-checks/{mail['candidate_id']}", allow_404=True)
    if bg and bg["status"] != "CLEAR":
        fatal.append(("background", f"バックグラウンドチェックで確認事項あり（{bg.get('note', '')}）"))

    issues = fatal + fixable
    texts = [t for _, t in issues]
    if not issues:
        subject, status = f"Re: {mail['subject']} - 内定のご連絡", "APPROVED"
        body = (f"{applicant} 様\n\nこの度は入社手続き書類をご提出いただきありがとうございます。\n"
                f"書類審査の結果、すべての要件を満たしていることを確認いたしました。\n"
                f"【{ht}】として採用が確定しましたことをお知らせいたします。\n\n"
                f"入社日の詳細、オリエンテーションのご案内、社内システムのアカウント情報は追ってご連絡いたします。\n"
                f"今後ともよろしくお願いいたします。\n\n人事部 入社手続き担当")
        detail = "全要件を満たすため採用確定メールを送信"
    else:
        subject, status = f"Re: {mail['subject']} - 選考結果のご連絡", "REJECTED"
        tail = ("誠に残念ながら、今回は採用要件を満たさないため、採用を見送らせていただくこととなりました。" if fatal else
                "上記書類をご修正のうえ、再度ご提出をお願いいたします（再提出後に改めて審査いたします）。")
        body = (f"{applicant} 様\n\nこの度は入社手続き書類をご提出いただきありがとうございます。\n"
                f"書類を確認した結果、以下の点で要件を満たしておりませんでした。\n\n"
                + "\n".join(f"  ・{t}" for t in texts) + f"\n\n{tail}\n\n人事部 入社手続き担当")
        detail = "不適格: " + " / ".join(texts) + ("（再提出可）" if not fatal else "")

    ref = notify(api, case, mail["from"], subject, body, "onboarding_result", in_reply_to=mail["id"])
    api.post(f"/mail/{mail['id']}/move", {"folder": "processed", "replied": True})
    archive_memo(api, cfg, row, "onboarding", status, [f"応募者: {applicant} ({ht})", f"経験年数: {exp_years}", f"検出事項: {texts or 'なし'}"], ref)
    return Result(status, detail, ref, codes=[c for c, _ in issues])
