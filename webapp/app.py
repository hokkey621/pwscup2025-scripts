"""Streamlitアプリ本体。"""

from __future__ import annotations

from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from webapp import APP_DESCRIPTION, APP_TITLE
from webapp import DEFAULT_BI_PATH
from webapp import anonymize
from webapp import evaluate


def _apply_pending_inputs() -> None:
    pending = st.session_state.pop("pending_inputs", None)
    if not pending:
        return

    for col, value in pending.items():
        st.session_state[f"input_{col}"] = value


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
    if "eval_result" not in st.session_state:
        st.session_state.eval_result = None


def render_form(profiles: dict[str, anonymize.ColumnProfile]) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    for col, profile in profiles.items():
        key = f"input_{col}"
        if profile.kind == "int":
            min_value = int(min(profile.min_value or 0, 0))
            max_base = profile.max_value or 100
            margin = max(10, int(max_base * 0.2))
            max_value = int(max_base + margin)
            entry[col] = st.number_input(
                col,
                min_value=min_value,
                max_value=max_value,
                step=1,
                value=int(st.session_state[key]),
                key=key,
            )
        elif profile.kind == "float":
            min_value = float(min(profile.min_value or 0.0, 0.0))
            max_base = profile.max_value or 100.0
            margin = max(5.0, max_base * 0.2)
            max_value = float(max_base + margin)
            entry[col] = st.number_input(
                col,
                min_value=min_value,
                max_value=max_value,
                value=float(st.session_state[key]),
                step=0.1,
                format="%.2f",
                key=key,
            )
        else:
            help_text = None
            if profile.examples:
                help_text = "例: " + ", ".join(profile.examples)
            entry[col] = st.text_input(
                col,
                value=str(st.session_state[key]),
                key=key,
                help=help_text,
            )
    return entry


def render_anonymization_panel() -> None:
    st.subheader("ペイン1：模擬電子カルテ（入力側）")
    st.caption("Biスキーマに沿った1行分のデータを入力してください。特異な値での実験も可能です。")

    message = st.session_state.pop("status_message", None)
    if message:
        st.success(message)

    profiles = st.session_state.column_profiles
    entry_values = render_form(profiles)

    algorithm = st.radio(
        "匿名化アルゴリズム",
        options=[opt[0] for opt in anonymize.ALGORITHM_OPTIONS],
        format_func=lambda key: anonymize.ALGORITHM_LABELS[key],
        key="selected_algorithm",
    )

    col_reset, col_execute = st.columns([1, 2])
    with col_reset:
        if st.button("入力を初期値に戻す", key="reset_inputs"):
            defaults = anonymize.default_form_values(profiles)
            st.session_state.pending_inputs = defaults
            st.session_state.status_message = "入力値を初期状態に戻しました。"
            st.rerun()

    with col_execute:
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
                st.session_state.bi_prime = result.bi_prime
                st.session_state.ci = result.ci
                st.session_state.new_row_index = result.new_index
                st.session_state.eval_result = None
                st.session_state.pending_inputs = result.entry
                st.session_state.status_message = "匿名化処理が完了しました。ペイン2とペイン3を確認してください。"
                st.rerun()


def render_ci_panel() -> None:
    st.subheader("ペイン2：匿名化データ（Ci）ビュー")
    if st.session_state.ci is None:
        st.info("先に『[ 1. 匿名化実行 ]』を押してください。")
        return

    ci_df: pd.DataFrame = st.session_state.ci
    bi_prime: pd.DataFrame = st.session_state.bi_prime
    new_idx: int = st.session_state.new_row_index

    st.caption("匿名化後のCi全体（末尾5行を表示）")
    st.dataframe(ci_df.tail(5), use_container_width=True)

    comparison = pd.concat(
        {
            "Bi'": bi_prime.loc[new_idx],
            "Ci": ci_df.loc[new_idx],
        },
        axis=1,
    )
    st.caption("新規行のビフォー・アフター")
    st.dataframe(comparison.T, use_container_width=True)


def render_evaluation_panel() -> None:
    st.subheader("ペイン3：PWS CUP 2025 評価ビュー")

    if st.button("[ 2. スコア計算実行 ]", key="start_evaluation"):
        if st.session_state.ci is None or st.session_state.bi_prime is None:
            st.warning("匿名化データがありません。先にペイン1で処理を実行してください。")
        else:
            with st.spinner("評価スクリプトを実行中..."):
                try:
                    result = evaluate.run_evaluation(
                        st.session_state.bi_prime,
                        st.session_state.ci,
                    )
                except evaluate.EvaluationError as exc:
                    st.error(f"評価に失敗しました: {exc}")
                else:
                    st.session_state.eval_result = result
                    st.success("評価が完了しました。")

    result: evaluate.EvaluationResult | None = st.session_state.eval_result
    if result is None:
        st.info("スコアを表示するには評価を実行してください。")
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

    with st.expander("評価ログ (uv run の標準出力)"):
        for label, text in result.logs.items():
            st.markdown(f"**{label}**")
            st.code(text or "(出力なし)")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    st.title(APP_TITLE)
    st.write(APP_DESCRIPTION)
    st.caption(f"Bi参照ファイル: {DEFAULT_BI_PATH}")

    col1, col2, col3 = st.columns(3)
    with col1:
        render_anonymization_panel()
    with col2:
        render_ci_panel()
    with col3:
        render_evaluation_panel()


if __name__ == "__main__":
    main()
