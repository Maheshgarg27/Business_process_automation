"""
Japanese -> English for what the platform shows on screen (mails, reasons, sheet values).

Every sentence the platform writes comes from a fixed template, so a phrase table is enough:
no external service, no API key, and it works offline. Dynamic parts (amounts, ids, dates) are left untouched.
Names are romanised with a small dictionary. Anything unknown stays as it is.
"""
import re

FAMILY = {"田中": "Tanaka", "佐藤": "Sato", "鈴木": "Suzuki", "高橋": "Takahashi", "伊藤": "Ito", "渡辺": "Watanabe",
          "山本": "Yamamoto", "中村": "Nakamura", "小林": "Kobayashi", "加藤": "Kato", "吉田": "Yoshida", "山田": "Yamada",
          "松本": "Matsumoto", "井上": "Inoue", "木村": "Kimura", "斎藤": "Saito", "清水": "Shimizu", "林": "Hayashi"}
GIVEN = {"太郎": "Taro", "花子": "Hanako", "健一": "Kenichi", "美咲": "Misaki", "翔太": "Shota", "陽子": "Yoko", "蓮": "Ren",
         "結衣": "Yui", "大輝": "Daiki", "彩": "Aya", "拓也": "Takuya", "直樹": "Naoki", "真由": "Mayu", "優子": "Yuko",
         "誠": "Makoto", "恵": "Megumi"}
_NAME = re.compile("(" + "|".join(FAMILY) + r") (" + "|".join(GIVEN) + ")")

# ---- structural rules (run first) ----
RULES = [
    (r"^(\s*)・", r"\1- "),
    (r"^(.+?) ご担当者様$", r"Dear \1 team,"),
    (r"^ご担当者様$", "Dear approver,"),
    (r"^人事ご担当者様$", "Dear HR team,"),
    (r"^(.+?) 様$", r"Dear \1,"),
    (r"お世話になっております。(.+?)です。", r"Thank you for your continued support. This is \1."),
    (r"【([^】]+)】として採用が確定しましたことをお知らせいたします。", r"We are pleased to inform you that you are hired as \1."),
    (r"(\d{4}-\d{2}-\d{2})の「(.+?)」を承認しました。（(.*?)）", r'Your "\2" request for \1 has been approved. (\3)'),
    (r"(\d{4}-\d{2}-\d{2})の「(.+?)」申請は以下の理由により承認できませんでした。", r'Your "\2" request for \1 could not be approved for the following reasons.'),
    (r"(\S+)は(部長|役員)承認が必要（現状: (.+?)）", r"\1 requires \2 approval (current: \3)"),
    (r"取引先(\d+)株式会社", r"Vendor \1 Co., Ltd."),
    (r" 否認$", " - denied"), (r" 承認$", " - approved"), (r" 要確認$", " - needs review"),
]

# ---- phrase table (longest match first) ----
P = {
    # onboarding
    "提出書類不足: ": "Missing document: ", "氏名不一致: ": "Name mismatch: ", "の発行日が古い（": " issue date is too old (",
    "日前／有効": " days ago / valid for ", "日以内）": " days)", "に署名がありません": " is not signed",
    "本人確認書類の有効期限切れ": "ID document has expired", "年齢要件を満たしていません（": "Age requirement not met (",
    "歳以上）": " years or older)", "経験年数不足（必要": "Insufficient experience (required ", "年／実績": " years / actual ",
    "バックグラウンドチェックで確認事項あり（": "Background check flagged an issue (", "前職照会で確認事項あり": "issue found in the previous-employer reference check",
    "契約期間の記載がありません": "Contract period is not stated", "全要件を満たすため採用確定メールを送信": "All requirements met; hiring confirmation mail sent",
    "受信箱に該当の応募メールが見つかりません（要確認）": "Application mail not found in the inbox (needs check)",
    "受信箱に該当の応募メールが見つかりません": "Application mail not found in the inbox",
    "不適格: ": "Not eligible: ", "（再提出可）": " (resubmission possible)", "応募者: ": "Applicant: ", "検出事項: ": "Findings: ",
    "この度は入社手続き書類をご提出いただきありがとうございます。": "Thank you for submitting your onboarding documents.",
    "書類審査の結果、すべての要件を満たしていることを確認いたしました。": "As a result of the document review, we confirmed that all requirements are met.",
    "入社日の詳細、オリエンテーションのご案内、社内システムのアカウント情報は追ってご連絡いたします。": "Details of your start date, orientation and your internal system account will follow.",
    "今後ともよろしくお願いいたします。": "We look forward to working with you.",
    "人事部 入社手続き担当": "HR Department, Onboarding",
    "書類を確認した結果、以下の点で要件を満たしておりませんでした。": "After reviewing the documents, the following requirements were not met.",
    "誠に残念ながら、今回は採用要件を満たさないため、採用を見送らせていただくこととなりました。": "Unfortunately, because the hiring requirements are not met, we must decline to proceed with your application this time.",
    "上記書類をご修正のうえ、再度ご提出をお願いいたします（再提出後に改めて審査いたします）。": "Please correct the documents above and submit them again (we will review again after resubmission).",
    "入社手続きに必要な書類を添付いたします。ご確認のほどよろしくお願いいたします。": "I am attaching the documents required for onboarding. Thank you for your review.",
    "（雇用区分: ": "(Employment type: ", "【入社手続き書類のご提出】": "[Submission of onboarding documents] ",
    " - 内定のご連絡": " - Offer notification", " - 選考結果のご連絡": " - Selection result",
    "【書類種別】": "[Document type] ", "署名: 済": "Signature: signed", "署名: 未": "Signature: not signed",
    "経験年数": "Years of experience", "生年月日": "Date of birth", "有効期限": "Expiry date", "発行日": "Issue date",
    "契約期間: 6ヶ月": "Contract period: 6 months", "扶養家族人数": "Number of dependents", "氏名": "Name",
    "契約開始日": "Contract start", "契約終了日": "Contract end", "契約上限額": "Contract ceiling",
    # documents
    "履歴書": "Resume", "職務経歴書": "Career history", "卒業（見込）証明書": "Graduation (expected) certificate",
    "本人確認書類": "ID document", "内定承諾書": "Offer acceptance", "雇用契約書（署名済）": "Signed employment contract",
    "給与振込口座届": "Bank account form", "健康診断書": "Health check certificate", "源泉徴収票": "Withholding tax slip",
    "扶養控除等申告書": "Dependent deduction form", "住民票": "Residence certificate",
    "新卒家族持": "New graduate with family", "新卒": "New graduate", "中途": "Mid-career", "契約社員": "Contract employee",
    # invoice
    "3点照合（請求書・発注書・検収・契約書）一致。差異なし": "Three-way match (invoice / PO / receipt / contract) agrees. No discrepancy",
    "差異あり・要確認: ": "Discrepancy found - needs review: ", " がERPに存在しません": " does not exist in the ERP",
    "請求書PDFが共有ドライブにありません": "Invoice PDF not found on the shared drive", "取引先が有効でありません": "Vendor is not active",
    "シート金額(": "Sheet amount (", ")とERP登録金額(": ") and ERP amount (", ")が不一致": ") do not match",
    "二重請求の疑い（支払済/承認済の同一請求: ": "Suspected duplicate invoice (same invoice already paid/approved: ",
    "対応する発注書(PO ": "Matching purchase order (PO ", ")が存在しません": ") does not exist",
    "検収（入荷）記録がありません": "No goods-receipt record", "請求書PDFの金額(": "Invoice PDF amount (", ")がERP金額(": ") vs ERP amount (",
    ")と不一致": ") do not match", "請求書PDFのPO番号(": "Invoice PDF PO number (", ")がERPと不一致": ") does not match the ERP",
    "請求額と発注額に差異 ": "Difference between invoice and PO amount ", "（許容": " (tolerance ", "契約書 ": "Contract ",
    " が共有ドライブにありません": " not found on the shared drive", "請求額が契約上限額を超過": "Invoice amount exceeds the contract ceiling",
    "請求額が検収額を超過 ": "Invoice amount exceeds received amount by ", "請求日が契約期間外（": "Invoice date is outside the contract period (",
    "【請求書のご確認】": "[Invoice confirmation] ", "請求書 ": "Invoice ", " について、以下の点を確認させてください。": " - please confirm the following points.",
    "ご確認のうえ、修正版のご送付をお願いいたします。": "Please review and send a corrected version.", "経理部 買掛金担当": "Accounting Dept., Accounts Payable",
    "請求書: ": "Invoice: ",
    # leave
    "HRシステムに該当の休暇申請がありません": "Leave request not found in the HR system", "却下: ": "Rejected: ",
    "申請日が処理基準日以前です": "Requested date is on or before the processing date", "上長承認が未完了": "Manager approval is incomplete",
    "前年度出勤率": "Previous-year attendance ", "（付与要件": " (below the required ", "未満）": ")",
    "有給残日数不足（残": "Insufficient paid-leave balance (remaining ", "日／申請": " days / requested ", "日）": " days)",
    "同日の部門欠勤上限超過（": "Department absence limit exceeded that day (", "名／上限": " absent / limit ", "名）": " people)",
    "半日有給の年間上限（": "Yearly half-day limit (", "回）に到達": " times) reached",
    "慶弔区分が就業規則に該当しません": "Event type is not covered by the work rules", "）の付与上限": ") grant limit ", "日を超過（申請": " days exceeded (requested ",
    "証明書類が共有ドライブにありません": "Proof document not found on the shared drive", "証明書類の内容（": "Proof document content (",
    "）が申請内容と一致しません": ") does not match the request", "勤怠データに未消化の休日出勤実績がありません": "No unused holiday-work record in the attendance data",
    "休日出勤実績が代休取得期限（": "Holiday-work record is past the comp-day deadline (", "日）を超過": " days)",
    "コアタイム（": "Core time (", "）を満たしていません（申請 ": ") is not covered (requested ", "月間変更回数の上限（": "Monthly change limit (",
    "未対応の休暇区分: ": "Unsupported leave type: ", "要件は充足。": "Requirements are met. ", "のため保留（承認依頼を送付）": " - on hold (approval request sent)",
    "要確認: ": "Needs review: ", "承認（": "Approved (", "有給残 ": "Paid leave remaining ", "休日出勤日 ": "Holiday-work day ",
    " を代休に充当": " applied to comp day", "フレックス勤務パターンを更新": "Flex work pattern updated", "特別休暇として付与": "Granted as special leave",
    "【休暇申請結果】": "[Leave request result] ", "【休暇申請】": "[Leave request] ", "内容をご確認のうえ再申請ください。": "Please review and resubmit.",
    "人事部 勤怠担当": "HR Dept., Attendance", "／": " / ",
    "年次有給休暇": "Annual paid leave", "半日有給申請": "Half-day paid leave", "特別休暇（慶弔）": "Special leave (ceremonial)",
    "代休申請": "Compensatory day-off", "フレックス変更申請": "Flex-time change", "休日出勤": "Holiday work",
    "結婚": "Marriage", "忌引": "Bereavement", "本人": "Self", "配偶者": "Spouse", "父母": "Parents", "祖父母": "Grandparents", "兄弟姉妹": "Siblings",
    "事由": "Reason", "続柄": "Relationship", "発生日": "Date of event",
    # expense
    "経費システムに該当の申請がありません": "Claim not found in the expense system", "【注意】": " [Note] ",
    "適格請求書発行事業者番号なし（仕入税額控除の対象外）": "No qualified-invoice registration number (not eligible for input tax deduction)",
    "事前申請（出張/研修承認）がありません": "No pre-approval (trip/training approval)", "【経費精算結果】": "[Expense result] ",
    "経費申請（": "Expense claim (", "）の審査結果: ": ") review result: ", "経理部 経費精算担当": "Accounting Dept., Expense Processing",
    ")と申請金額(": ") and claim amount (", "の上限": " limit ", "を超過（": " exceeded (", "承認待ち（承認依頼を送付）: ": "Awaiting approval (approval request sent): ",
    "／方針内）": " / within policy)", "領収書ファイルがありません（": "Receipt file not found (receipt required above ", "超は必須）": ")",
    "領収書の金額(": "Receipt amount (", ")が申請金額(": ") differs from claim amount (", "領収書日付から": "Receipt date is ", "日経過（申請期限": " days old (deadline ",
    "領収書 ": "Receipt ", " は精算済み（二重申請）": " was already reimbursed (duplicate claim)",
    "超のため上長承認が必要（未承認）": " exceeded - manager approval required (not approved)", "1人当たり": "Per person ", "が上限": " exceeds the limit ",
    "超（参加": " (attendees ", "接待交際費": "Entertainment", "出張旅費": "Business travel", "研修費": "Training", "消耗品費": "Consumables", "交通費精算": "Local transport",
    # inventory
    "WMSに該当の調整依頼または在庫マスタがありません": "Adjustment request or stock master not found in the WMS", "廃棄理由コードが未入力": "Scrap reason code is missing",
    "／安全在庫割れ→補充アラート発行": " / below safety stock -> replenishment alert issued", "品目名が不一致（WMS: ": "Item name mismatch (WMS: ", "／シート: ": " / sheet: ",
    "引当分を除く利用可能在庫が不足（利用可能": "Insufficient available stock excluding reserved (available ", "／要求": " / requested ",
    "実地棚卸シートが共有ドライブにありません": "Physical count sheet not found on the shared drive", "大口調整（現在庫の": "Large adjustment (",
    "）のため倉庫責任者の承認が必要": " of current stock) - warehouse manager approval required", "個を反映（在庫 ": " units applied (stock ",
    "調整後在庫がマイナスになります（現在庫": "Stock would become negative after adjustment (current stock ", "／調整": " / adjustment ",
    "棚卸差異（": "Count difference (", "）が調整依頼（": ") vs adjustment request (", "）と一致しません": ") do not match",
    "制御基板ユニットA": "Control board unit A", "電源モジュールB": "Power module B", "センサーC": "Sensor C", "ケーブルセットD": "Cable set D",
    "筐体パネルE": "Chassis panel E", "ファンユニットF": "Fan unit F", "コネクタG": "Connector G", "ブラケットH": "Bracket H", "特注部品I": "Custom part I",
    # budget
    "元帳に該当の予算行がありません（部門・予算額で照合）": "Budget line not found in the ledger (matched by department and budget)",
    "総勘定元帳エクスポート（": "General-ledger export (", "）が見つかりません": ") not found", "予算内（差異 ": "Within budget (variance ",
    "%、許容±": "%, tolerance ±", "差異は受け入れられません: ": "Variance not accepted: ", "シートと元帳の実績が不一致（元帳": "Actual differs between sheet and ledger (ledger ",
    "／シート": " / sheet ", "差異率が再計算値と相違（シート": "Variance rate differs from recomputed value (sheet ", "%／再計算": "% / recomputed ",
    "差異 ": "Variance ", "%（予算": "% (budget ", "超過": "overspend", "未消化": "underspend", "）— 是正・役員報告が必要": ") - corrective action and executive report required",
    "% — 部門長によるコメント記入が必要": "% - the department head must add a comment",
    "承認待ち（部門長へ確認依頼を送付）: ": "Awaiting approval (confirmation request sent to the department head): ", "データ不整合のため要確認: ": "Needs review due to data inconsistency: ",
    "営業部": "Sales", "開発部": "Development", "管理部": "Administration", "物流部": "Logistics", "製造部": "Manufacturing", "人事部": "HR", "経理部": "Accounting",
    # orders
    "部長": "Manager", "役員": "Executive", "年間契約": "Annual contract", "定期発注": "Regular order", "スポット発注": "Spot order", "緊急発注": "Urgent order",
    "緊急": "Urgent", "通常": "Normal", "購買依頼が調達システムに存在しません": "Purchase request not found in the procurement system",
    "緊急発注の理由書がありません": "No written justification for the urgent order", "取引先 ": "Vendor ", " が取引停止中": " is suspended", "見積書 ": "Quotation ",
    "承認なし": "no approval", "再確認が必要: ": "Needs re-check: ", "見積の有効期限切れ（": "Quotation has expired (", "見積金額との差異 ": "Difference from quoted amount ",
    "の許容±": " tolerance ±", "年間契約の残枠不足（残": "Annual contract remaining limit insufficient (remaining ", "／今回": " / this order ",
    "発注登録時に契約枠超過: ": "Contract limit exceeded at PO registration: ", "契約単価表（": "Contract price list (", "円）と見積単価（": " JPY) vs quoted unit price (",
    "円）が相違": " JPY) differ", "発注確定 ": "Order confirmed ", "個 ": " units ", "／緊急のため優先処理": " / urgent - priority handling",
    "【発注書】": "[Purchase order] ", "下記のとおり発注いたします。": "We place the following order.", "発注番号: ": "PO number: ", "品目: ": "Item: ",
    "数量: ": "Quantity: ", "金額: ": "Amount: ", "区分: ": "Type: ", "ご確認をお願いいたします。": "Please confirm.", "購買部": "Purchasing Dept.",
    "事務用品": "Office supplies", "梱包材料": "Packing materials", "工場設備部品": "Factory equipment parts", "電子基板ユニット": "Electronic board unit",
    "包装資材": "Packaging materials", "サーバー保守部品": "Server maintenance parts", "測定機器": "Measuring equipment",
    # workflow mails
    "【承認依頼】": "[Approval request] ", "以下の案件は、規定上ご承認が必要です。": "The following case requires your approval under company policy.",
    "案件ID: ": "Case ID: ", "内容: ": "Details: ",
    "承認する場合は本メールに「APPROVE」、却下する場合は「REJECT」と1行目に記入して返信してください。": "To approve, reply to this mail with APPROVE on the first line; to reject, reply with REJECT.",
    "返信内容は次回の自動処理で反映されます。": "Your reply will be applied in the next automated run.", "給与業務自動化システム": "Payroll Process Automation System",
    "【リマインド】承認依頼 ": "[Reminder] Approval request ", "案件 ": "Case ", " の承認をお願いします（": " - please approve (", "日経過）。": " days elapsed).",
    "【承認遅延のエスカレーション】": "[Escalation: approval delay] ", " の承認が ": " has been pending approval for ", " 日間未対応です（承認者: ": " days (approver: ", "）。ご確認ください。": "). Please check.",
    "確認しました。問題ありません。": "I have checked it. No problem.", "内容に問題があるため却下します。": "I reject this because of a problem with the content.",
    "6ヶ月": "6 months", "取引停止先株式会社": "Suspended Vendor Co., Ltd.", "／承認者: ": " / Approver: ",
}
_PHRASES = sorted(P.items(), key=lambda kv: -len(kv[0]))
_PUNCT = [("（", " ("), ("）", ")"), ("：", ": "), ("【", "["), ("】", "] "), ("「", '"'), ("」", '"'), ("〜", " to "), ("、", ", "), ("。", ". "), ("　", " "), ("・", ", ")]
_UNITS = [(r"(\d[\d,\.]*)円", r"\1 JPY"), (r"(\d[\d\.]*)日", r"\1 days"), (r"(\d[\d\.]*)年", r"\1 years"), (r"(\d+)名", r"\1 people"),
          (r"(\d+)個", r"\1 units"), (r"(\d+)回", r"\1 times"), (r"(\d+)歳", r"\1 years old")]
_CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def to_english(text):
    if text is None or not isinstance(text, str) or not _CJK.search(text):
        return text
    for pat, rep in RULES:
        text = re.sub(pat, rep, text, flags=re.M)
    text = _NAME.sub(lambda m: f"{GIVEN[m.group(2)]} {FAMILY[m.group(1)]}", text)
    for jp, en in _PHRASES:
        if jp in text:
            text = text.replace(jp, en)
    for jp, en in _PUNCT:
        text = text.replace(jp, en)
    for pat, rep in _UNITS:
        text = re.sub(pat, rep, text)
    text = re.sub(r"[ \t]+\)", ")", text)
    text = re.sub(r"\([ \t]+", "(", text)
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([,.:])", r"\1", text)
    return text


def leftover_japanese(text):
    """Japanese characters still present after translation (used by the self-check)."""
    return re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]+", to_english(text) or "")
