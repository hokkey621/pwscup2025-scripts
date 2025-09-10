# PWS Cup 2025 初心者向けガイド

## 概要
このガイドでは、PWS Cup 2025の加工フェーズにおけるハンズオン作業を初心者向けに説明します。ハワイ州のサンプルデータを使用して、匿名加工の実践的な体験を行います。

## 使用するファイルセット

### データファイル
- **HI_100K.csv**: データAi相当（100,000件のハワイ州患者データ）
- **HI_10k.csv**: データBi相当（10,000件のハワイ州患者データのサブセット）

### データ項目
両ファイルには以下の項目が含まれています：
- `GENDER`: 性別 (M/F)
- `AGE`: 年齢
- `RACE`: 人種 (asian, black, hawaiian, native, other, white)
- `ETHNICITY`: 民族 (hispanic/nonhispanic)
- `encounter_count`: 診察回数
- `num_procedures`: 処置数
- `num_medications`: 処方薬数
- `num_immunizations`: 予防接種数
- `num_allergies`: アレルギー数
- `num_devices`: デバイス数
- `asthma_flag`: 喘息フラグ (0/1)
- `stroke_flag`: 脳卒中フラグ (0/1)
- `obesity_flag`: 肥満フラグ (0/1)
- `depression_flag`: うつ病フラグ (0/1)
- `mean_systolic_bp`: 収縮期血圧平均
- `mean_diastolic_bp`: 拡張期血圧平均
- `mean_bmi`: BMI平均
- `mean_weight`: 体重平均

## 加工フェーズのハンズオン

### Step 1: 匿名化データ Ci の作成

HI_10k.csv を匿名加工してCi相当データを作成します。

```bash
python anonymization/ano.py data/HI_10k.csv HI_10k_anon.csv
```

#### 匿名加工の内容
- **カテゴリ項目**: GENDER, RACE, ETHNICITY を確率的に他の値に置換
- **年齢**: ±2歳のランダムノイズを追加（0-120歳でクリップ）
- **整数項目**: encounter_count, num_procedures等に範囲内でランダムノイズを追加
- **フラグ項目**: asthma_flag等を確率的に反転
- **実数項目**: 血圧、BMI、体重にランダムノイズを追加

#### Step 1-1: データ値域の確認

生成した匿名データが適切な値域内にあることを確認します。

```bash
python util/check_csv.py HI_10k_anon.csv data/pre_columns_range.json
```

##### 値域定義ファイル（pre_columns_range.json）の内容
各項目について以下が定義されています：
- **type**: データタイプ（number/category/date）
- **min/max**: 数値項目の最小値・最大値
- **values**: カテゴリ項目の許可される値
- **max_decimal_places**: 小数点以下の最大桁数

#### Step 1-2: 有用性評価の実行

BiとCiの有用性を評価します。

```bash
python evaluation/eval_all.py data/HI_10k.csv HI_10k_anon.csv
```

##### 評価項目
1. **基本統計の差異** (stats_diff): 統計量の最大絶対誤差
2. **ロジスティック回帰での差異** (LR_asthma_diff): 喘息予測モデルの差異
3. **独立性検定での差異** (KW_IND_diff): カテゴリ変数間の独立性の差異

##### スコア計算
```
Ci_utility = 40 × (1 - stats_diff_max_abs) + 
             20 × (1 - LR_asthma_diff_max_abs) + 
             20 × (1 - KW_IND_diff_max_abs)
```
最大80点で評価されます。

### Step 2: 機械学習モデル Di の作成

作成した匿名化データを使って機械学習モデルを構築します。

```bash
python analysis/xgbt_train.py HI_10k_anon.csv --model-json HI_10k_anon.json
```

#### 学習内容
- **アルゴリズム**: XGBoost（勾配ブースティング決定木）
- **目的変数**: stroke_flag（脳卒中フラグ）をデフォルトで使用
- **前処理**: 
  - 数値列とカテゴリ列を自動判定
  - カテゴリ列はone-hot encoding（drop_first=True）
  - ゼロ分散列の除去
  - 列名を昇順で固定

#### Step 2-1: 学習データでの評価確認

作成したモデルを学習データで評価してみます。

```bash
python analysis/xgbt_pred.py HI_10k_anon.json --target "stroke_flag" --test-csv HI_10k_anon.csv
```

#### Step 2-2: 大本データでの評価（参考）

大本のデータに対しても評価を試してみます。

```bash
python analysis/xgbt_pred.py HI_10k_anon.json --target "stroke_flag" --test-csv data/HI_100K.csv
```

**注意**: 実際の競技では、データAi（HI_100K.csv相当）は運営側のみが持つ情報のため、参加者はこの評価を実施できません。ここでは学習目的での参考実行となります。

## 実行例

```bash
# Step 1: 匿名化データ Ci の生成
python anonymization/ano.py data/HI_10k.csv HI_10k_anon.csv

# Step 1-1: データ値域の確認
python util/check_csv.py HI_10k_anon.csv data/pre_columns_range.json

# Step 1-2: 有用性評価
python evaluation/eval_all.py data/HI_10k.csv HI_10k_anon.csv

# Step 2: 機械学習モデル Di の作成
python analysis/xgbt_train.py HI_10k_anon.csv --model-json HI_10k_anon.json

# Step 2-1: 学習データでの評価確認
python analysis/xgbt_pred.py HI_10k_anon.json --target "stroke_flag" --test-csv HI_10k_anon.csv

# Step 2-2: 大本データでの評価（参考）
python analysis/xgbt_pred.py HI_10k_anon.json --target "stroke_flag" --test-csv data/HI_100K.csv
```

## 期待される出力

### Step 1-1: 値域確認の結果
```
全ての値が JSON 仕様内です。
```

### Step 1-2: 有用性評価の結果例
```
stats_diff max_abs: 0.1234
LR_asthma_diff max_abs: 0.0567
KW_IND_diff max_abs: 0.0890
Ci utility: 65.42 / 80
```

### Step 2: 機械学習モデル学習の結果例
```
Validation Accuracy (threshold=0.5): 0.925000
Saved model JSON to: HI_10k_anon.json
#features: 45
```

### Step 2-1: 学習データ評価の結果例
```
Accuracy (test, threshold=0.500): 0.928000
```

### Step 2-2: 大本データ評価の結果例
```
Accuracy (test, threshold=0.500): 0.890000
```

## ファイル構成

```
pwscup2025-scripts/
├── data/
│   ├── HI_100K.csv          # データAi相当
│   ├── HI_10k.csv           # データBi相当
│   └── pre_columns_range.json # 値域定義
├── anonymization/
│   └── ano.py               # 匿名加工スクリプト
├── util/
│   └── check_csv.py         # 値域確認スクリプト
├── evaluation/
│   └── eval_all.py          # 有用性評価スクリプト
├── analysis/
│   ├── xgbt_train.py        # 機械学習モデル学習スクリプト
│   └── xgbt_pred.py         # 機械学習モデル予測スクリプト
├── HI_10k_anon.csv          # 生成される匿名データ（Ci相当）
└── HI_10k_anon.json         # 生成される機械学習モデル（Di相当）
```

## 注意事項

1. 匿名加工時に `--seed` オプションを指定すると再現可能な結果が得られます
2. 各評価指標は0-1の範囲で出力され、小さいほど元データとの差異が少ないことを示します
3. 有用性スコアが高いほど、匿名化後も元データの有用性が保たれていることを示します

このガイドに沿って作業を進めることで、PWS Cup 2025の加工フェーズの基本的な流れを体験できます。