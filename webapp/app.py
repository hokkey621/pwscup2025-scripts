"""Streamlitアプリ本体。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from pandas.api import types as pdt
import streamlit as st

from webapp import APP_DESCRIPTION, APP_TITLE
from webapp import DEFAULT_BI_PATH
from webapp import anonymize
from webapp import evaluate


@dataclass
class RunRecord:
    """匿名化実行結果を保持する。"""

    run_id: int
    label: str
    algorithm: str
    bi_prime: pd.DataFrame
    ci: pd.DataFrame
    new_index: int
    entry: dict[str, Any]
    eval_result: evaluate.EvaluationResult | None = None

FIELD_LABELS: dict[str, str] = {
    "GENDER": "性別",
    "AGE": "年齢",
    "RACE": "人種区分",
    "ETHNICITY": "民族属性",
    "encounter_count": "受診回数",
    "num_procedures": "実施手技数",
    "num_medications": "処方薬剤数",
    "num_immunizations": "予防接種数",
    "num_allergies": "アレルギー登録数",
    "num_devices": "使用デバイス数",
    "asthma_flag": "喘息",
    "stroke_flag": "脳卒中",
    "obesity_flag": "肥満",
    "depression_flag": "うつ病",
    "mean_systolic_bp": "平均収縮期血圧",
    "mean_diastolic_bp": "平均拡張期血圧",
    "mean_bmi": "平均BMI",
    "mean_weight": "平均体重",
}

FIELD_HELP_TEXT: dict[str, str] = {
    "GENDER": "カルテ上の登録性別（M/F）。",
    "AGE": "受診時点の年齢。",
    "RACE": "米国HIPAA準拠の人種カテゴリー。",
    "ETHNICITY": "ヒスパニック/非ヒスパニック区分。",
    "encounter_count": "累計の受診（Encounters）件数。",
    "num_procedures": "診療時に実施した処置の累計。",
    "num_medications": "処方中の薬剤エントリ数。",
    "num_immunizations": "接種済みワクチン数。",
    "num_allergies": "登録済みアレルゲン数。",
    "num_devices": "装着/管理している医療デバイス数。",
    "mean_systolic_bp": "直近訪問の平均収縮期血圧 (mmHg)。",
    "mean_diastolic_bp": "直近訪問の平均拡張期血圧 (mmHg)。",
    "mean_bmi": "計測期間の平均BMI。",
    "mean_weight": "計測期間の平均体重 (kg)。",
}

BINARY_FLAG_FIELDS = {
    "asthma_flag",
    "stroke_flag",
    "obesity_flag",
    "depression_flag",
}

FORM_SECTIONS: list[dict[str, Any]] = [
    {
        "title": "① 基本プロフィール",
        "caption": "受付担当が確認する患者基本属性です。",
        "columns": 2,
        "fields": ["GENDER", "AGE", "RACE", "ETHNICITY"],
    },
    {
        "title": "② 受診歴／処置サマリ",
        "caption": "カルテの統計フィールドを参照しています。",
        "columns": 3,
        "fields": [
            "encounter_count",
            "num_procedures",
            "num_medications",
            "num_immunizations",
            "num_allergies",
            "num_devices",
        ],
    },
    {
        "title": "③ 既往歴フラグ",
        "caption": "疾患レジストリの登録状況です。",
        "columns": 2,
        "fields": [
            "asthma_flag",
            "stroke_flag",
            "obesity_flag",
            "depression_flag",
        ],
    },
    {
        "title": "④ バイタルサイン",
        "caption": "最近の平均値を入力・調整できます。",
        "columns": 2,
        "fields": [
            "mean_systolic_bp",
            "mean_diastolic_bp",
            "mean_bmi",
            "mean_weight",
        ],
    },
]

VIEW_OPTIONS: list[tuple[str, str]] = [
    ("entry", "カルテ入力"),
    ("result", "匿名化結果"),
]


def _apply_pending_inputs() -> None:
    pending = st.session_state.pop("pending_inputs", None)
    if not pending:
        return

    for col, value in pending.items():
        st.session_state[f"input_{col}"] = value


def _store_run_result(
    result: anonymize.AnonymizationResult, algorithm: str
) -> RunRecord:
    run_id = st.session_state.next_run_id
    label = f"Run {run_id}: {anonymize.ALGORITHM_LABELS.get(algorithm, algorithm)}"
    record = RunRecord(
        run_id=run_id,
        label=label,
        algorithm=algorithm,
        bi_prime=result.bi_prime,
        ci=result.ci,
        new_index=result.new_index,
        entry=result.entry,
    )
    st.session_state.run_history.append(record)
    st.session_state.next_run_id += 1
    st.session_state.bi_prime = result.bi_prime
    st.session_state.ci = result.ci
    st.session_state.new_row_index = result.new_index
    return record


def _values_changed(value_before: Any, value_after: Any) -> bool:
    if pd.isna(value_before) and pd.isna(value_after):
        return False
    return value_before != value_after


def init_state() -> None:
    if "base_bi" not in st.session_state:
        base_df = anonymize.load_base_bi(DEFAULT_BI_PATH)
        profiles = anonymize.build_column_profiles(base_df)
        st.session_state.base_bi = base_df
        st.session_state.column_profiles = profiles
    else:
        profiles = st.session_state.column_profiles

    defaults = anonymize.default_form_values(profiles)
    for col, default in defaults.items():
        key = f"input_{col}"
        if key not in st.session_state:
            st.session_state[key] = default

    _apply_pending_inputs()

    if "selected_algorithm" not in st.session_state:
        st.session_state.selected_algorithm = anonymize.ALGORITHM_OPTIONS[0][0]

    if "bi_prime" not in st.session_state:
        st.session_state.bi_prime = None
    if "ci" not in st.session_state:
        st.session_state.ci = None
    if "new_row_index" not in st.session_state:
        st.session_state.new_row_index = None
    if "current_view" not in st.session_state:
        st.session_state.current_view = VIEW_OPTIONS[0][0]
    if "run_history" not in st.session_state:
        st.session_state.run_history: list[RunRecord] = []
    if "next_run_id" not in st.session_state:
        st.session_state.next_run_id = 1


def _render_field_widget(col: str, profile: anonymize.ColumnProfile) -> Any:
    key = f"input_{col}"
    label = FIELD_LABELS.get(col, col)
    help_text = FIELD_HELP_TEXT.get(col)

    if col in BINARY_FLAG_FIELDS:
        return st.toggle(
            label,
            value=bool(st.session_state.get(key, False)),
            key=key,
            help=help_text,
        )

    if profile.kind == "int":
        min_value = int(min(profile.min_value or 0, 0))
        max_base = profile.max_value or 100
        margin = max(10, int(max_base * 0.2))
        max_value = int(max_base + margin)
        return st.number_input(
            label,
            min_value=min_value,
            max_value=max_value,
            step=1,
            value=int(st.session_state[key]),
            key=key,
            help=help_text,
        )

    if profile.kind == "float":
        min_value = float(min(profile.min_value or 0.0, 0.0))
        max_base = profile.max_value or 100.0
        margin = max(5.0, max_base * 0.2)
        max_value = float(max_base + margin)
        return st.number_input(
            label,
            min_value=min_value,
            max_value=max_value,
            value=float(st.session_state[key]),
            step=0.1,
            format="%.2f",
            key=key,
            help=help_text,
        )

    examples = list(dict.fromkeys(profile.examples))
    if examples:
        current = st.session_state.get(key, examples[0])
        index = examples.index(current) if current in examples else 0
        return st.selectbox(
            label,
            options=examples,
            index=index,
            key=key,
            help=help_text,
        )

    return st.text_input(
        label,
        value=str(st.session_state[key]),
        key=key,
        help=help_text,
    )


def render_emr_form(profiles: dict[str, anonymize.ColumnProfile]) -> dict[str, Any]:
    """電子カルテ風のセクションでフォームを描画する。"""

    entry: dict[str, Any] = {}
    covered: set[str] = set()
    for idx, section in enumerate(FORM_SECTIONS):
        st.markdown(f"#### {section['title']}")
        st.caption(section["caption"])
        cols = st.columns(section.get("columns", 2))
        for offset, field in enumerate(section["fields"]):
            if field not in profiles:
                continue
            covered.add(field)
            with cols[offset % len(cols)]:
                entry[field] = _render_field_widget(field, profiles[field])
        if idx < len(FORM_SECTIONS) - 1:
            st.divider()

    remaining_fields = [col for col in profiles.keys() if col not in covered]
    if remaining_fields:
        st.markdown("#### ⑤ その他の項目")
        st.caption("データセットに含まれる追加カラムです。")
        cols = st.columns(2)
        for offset, field in enumerate(remaining_fields):
            with cols[offset % len(cols)]:
                entry[field] = _render_field_widget(field, profiles[field])

    return entry


def render_anonymization_panel() -> None:
    st.subheader("電子カルテ入力シート")
    st.caption("実際のカルテ画面を意識した構成で、患者1件分の入力と匿名化を行います。")

    message = st.session_state.pop("status_message", None)
    if message:
        st.success(message)

    profiles = st.session_state.column_profiles
    with st.container(border=True):
        entry_values = render_emr_form(profiles)

    with st.container(border=True):
        st.markdown("#### 匿名化オプション")
        algorithm = st.radio(
            "アルゴリズム選択",
            options=[opt[0] for opt in anonymize.ALGORITHM_OPTIONS],
            format_func=lambda key: anonymize.ALGORITHM_LABELS[key],
            key="selected_algorithm",
        )

        col_reset, col_single, col_all = st.columns([1, 1.5, 1.5])
        with col_reset:
            if st.button("入力を初期値に戻す", key="reset_inputs"):
                defaults = anonymize.default_form_values(profiles)
                st.session_state.pending_inputs = defaults
                st.session_state.status_message = "入力値を初期状態に戻しました。"
                st.rerun()

        with col_single:
            if st.button("[ 1. 匿名化実行 ]", type="primary"):
                try:
                    result = anonymize.run_anonymization(
                        st.session_state.base_bi,
                        profiles,
                        entry_values,
                        algorithm,
                    )
                except anonymize.AnonymizationError as exc:
                    st.error(f"入力にエラーがあります: {exc}")
                else:
                    _store_run_result(result, algorithm)
                    st.session_state.pending_inputs = result.entry
                    st.session_state.status_message = (
                        f"{anonymize.ALGORITHM_LABELS.get(algorithm, algorithm)}で匿名化しました。"
                    )
                    st.session_state.current_view = "result"
                    st.rerun()

        with col_all:
            if st.button("[ 1. 全手法で匿名化 ]"):
                try:
                    results = [
                        (
                            algo,
                            anonymize.run_anonymization(
                                st.session_state.base_bi,
                                profiles,
                                entry_values,
                                algo,
                            ),
                        )
                        for algo, _ in anonymize.ALGORITHM_OPTIONS
                    ]
                except anonymize.AnonymizationError as exc:
                    st.error(f"入力にエラーがあります: {exc}")
                else:
                    last_entry = None
                    for algo, algo_result in results:
                        _store_run_result(algo_result, algo)
                        last_entry = algo_result.entry
                    if last_entry is not None:
                        st.session_state.pending_inputs = last_entry
                    labels = [
                        anonymize.ALGORITHM_LABELS.get(algo, algo)
                        for algo, _ in anonymize.ALGORITHM_OPTIONS
                    ]
                    st.session_state.status_message = (
                        f"全{len(labels)}手法で匿名化しました: {', '.join(labels)}"
                    )
                    st.session_state.current_view = "result"
                    st.rerun()


def render_ci_panel(record: RunRecord) -> None:
    st.markdown("#### 匿名化データの差分")

    ci_df: pd.DataFrame = record.ci
    bi_prime: pd.DataFrame = record.bi_prime
    new_idx: int = record.new_index

    diff_rows: list[dict[str, Any]] = []
    change_mask: list[bool] = []
    changed_count = 0
    for col in ci_df.columns:
        before = bi_prime.at[new_idx, col]
        after = ci_df.at[new_idx, col]
        changed = _values_changed(before, after)
        if changed:
            changed_count += 1

        delta_display = ""
        if (
            pdt.is_numeric_dtype(ci_df[col])
            and pd.notna(before)
            and pd.notna(after)
        ):
            diff_value = float(after) - float(before)
            if abs(diff_value) > 1e-9:
                if pdt.is_integer_dtype(ci_df[col]):
                    delta_display = f"{diff_value:+.0f}"
                else:
                    delta_display = f"{diff_value:+.2f}"

        diff_rows.append(
            {
                "項目": FIELD_LABELS.get(col, col),
                "Bi'": before,
                "Ci": after,
                "差分": delta_display,
            }
        )
        change_mask.append(changed)

    st.metric("変更された項目数", f"{changed_count} / {len(diff_rows)}")
    diff_df = pd.DataFrame(diff_rows).set_index("項目")

    def _highlight(row: pd.Series) -> list[str]:
        idx = diff_df.index.get_loc(row.name)
        if change_mask[idx]:
            return ["background-color: rgba(255, 221, 170, 0.6)"] * len(row)
        if idx == len(diff_df) - 1:
            return ["background-color: rgba(230, 240, 255, 0.5)"] * len(row)
        return ["" for _ in row]

    styled = diff_df.style.format(precision=2).apply(_highlight, axis=1)
    st.dataframe(styled, use_container_width=True)


def _run_evaluation_for_record(record: RunRecord) -> None:
    with st.spinner(
        f"[{record.label}] PWS CUP 2025 評価スクリプトを実行中..."
    ):
        try:
            result = evaluate.run_evaluation(
                record.bi_prime,
                record.ci,
            )
        except evaluate.EvaluationError as exc:
            st.error(f"{record.label} の評価に失敗しました: {exc}")
        else:
            record.eval_result = result
            st.success(f"{record.label} の評価が完了しました。")


def render_evaluation_panel(record: RunRecord) -> None:
    st.markdown("#### 評価スコア")

    button_key = f"start_evaluation_{record.run_id}"
    if st.button("[ 2. スコア計算実行 ]", key=button_key):
        _run_evaluation_for_record(record)

    result: evaluate.EvaluationResult | None = record.eval_result
    if result is None:
        st.info("評価実行後にスコアが表示されます。")
        return

    col_utility, col_privacy, col_acc = st.columns(3)

    with col_utility:
        if result.utility_score is not None:
            st.metric("有用性スコア", f"{result.utility_score:.2f}")
        else:
            st.metric("有用性スコア", "取得失敗")

    with col_privacy:
        if result.privacy_score is not None:
            st.metric("匿名性スコア", f"{result.privacy_score * 100:.1f}%")
        else:
            st.metric("匿名性スコア", "取得失敗")

    with col_acc:
        if result.validation_accuracy is not None:
            st.metric("Di検証精度", f"{result.validation_accuracy:.3f}")
        else:
            st.metric("Di検証精度", "取得失敗")

    if result.attack_success_total is None or result.attack_success_total == 0:
        st.success(result.mia_message)
    else:
        st.warning(result.mia_message)

    with st.expander("評価ログ (uv run 標準出力)"):
        for label, text in result.logs.items():
            st.markdown(f"**{label}**")
            st.code(text or "(出力なし)")


def render_result_screen() -> None:
    st.subheader("匿名化結果ビュー")
    runs: list[RunRecord] = st.session_state.run_history
    if not runs:
        st.info("まだ匿名化結果がありません。カルテ入力画面で処理を実行してください。")
        return

    st.markdown("#### 一括評価")
    col_eval_all, col_summary = st.columns([1.5, 2])
    with col_eval_all:
        if st.button("[ 2. 全手法の評価を実行 ]"):
            for record in runs:
                _run_evaluation_for_record(record)
            st.rerun()
    with col_summary:
        st.info("評価結果の詳細は各タブ下部に表示されます。")

    labels = [record.label for record in runs]
    tabs = st.tabs(labels)
    for tab, record in zip(tabs, runs):
        with tab:
            st.caption(
                f"アルゴリズム: {anonymize.ALGORITHM_LABELS.get(record.algorithm, record.algorithm)}"
            )
            with st.container(border=True):
                render_ci_panel(record)
            with st.container(border=True):
                render_evaluation_panel(record)
            st.markdown("##### 評価指標の説明")
            st.markdown(
                """
                - **有用性** \\(U\\): Bi' で訓練した予測器の性能差分。Codabench評価式に従い \\(U = 1 - \\Delta \\text{loss}\\) として計算され、値が高いほどCiでも実用的です。
                - **匿名性** \\(P\\): PWS CUP プライバシースコア。攻撃成功率 \\(A\\) に対して \\(P = 1 - A\\)（百分率表示）となり、100%に近いほど安全です。
                - **Di精度** \\(Acc_{Di}\\): 攻撃モデル（Di）の検証精度。\\(Acc_{Di} = \\frac{TP + TN}{TP + TN + FP + FN}\\)。低いほど攻撃が失敗している状態です。
                - **MIA結果**: 上記指標を踏まえた Membership Inference Attack の解釈コメントです。
                """
            )
            rendered_summary = {
                "Run": record.label,
                "有用性": "未評価",
                "匿名性": "未評価",
                "Di精度": "未評価",
                "MIA結果": "未評価",
            }
            if record.eval_result:
                res = record.eval_result
                rendered_summary["有用性"] = (
                    f"{res.utility_score:.2f}"
                    if res.utility_score is not None
                    else "N/A"
                )
                rendered_summary["匿名性"] = (
                    f"{res.privacy_score * 100:.1f}%"
                    if res.privacy_score is not None
                    else "N/A"
                )
                rendered_summary["Di精度"] = (
                    f"{res.validation_accuracy:.3f}"
                    if res.validation_accuracy is not None
                    else "N/A"
                )
                rendered_summary["MIA結果"] = res.mia_message or "N/A"
            st.markdown("##### 評価サマリ")
            st.table(
                pd.DataFrame([rendered_summary]).set_index("Run"),
            )


def render_navigation() -> None:
    st.markdown("### 画面切替")
    cols = st.columns(len(VIEW_OPTIONS))
    for col, (value, label) in zip(cols, VIEW_OPTIONS):
        is_active = st.session_state.current_view == value
        button_label = f"● {label}" if is_active else label
        if col.button(
            button_label,
            use_container_width=True,
            disabled=is_active,
            key=f"nav_{value}",
        ):
            st.session_state.current_view = value
            st.rerun()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.title(APP_TITLE)
    st.write(APP_DESCRIPTION)
    st.caption(f"Bi参照ファイル: {DEFAULT_BI_PATH}")

    render_navigation()

    if st.session_state.current_view == "entry":
        render_anonymization_panel()
    else:
        render_result_screen()


if __name__ == "__main__":
    main()
