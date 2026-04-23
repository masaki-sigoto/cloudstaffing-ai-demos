# 技術仕様書レビュー履歴ログ

対象ドキュメント: `03_spec.md`（CSV加工の完全自動化・勤怠CSV自動整形デモ）

---

## ラウンド1（Codex、2026-04-23）

### 総合評価
**C** — 設計書との骨格整合は高いが、実装直前仕様としては「実装不能/誤実装を招く矛盾が4点」あり。このままPhase5に入ると `keep/fail` 系とセキュリティガードで高確率で手戻りする。

### Critical 指摘
1. **`ReviewCell.reason` の情報源が型に存在しない**（A/B/G）
   - `NormalizedCell` が `reason` を持たないため、`ReviewCollector` が `ReviewCell(reason)` を再構成不能。
   - 修正方針: `NormalizedCell` に `review_reason: str | None` を追加。
2. **`DateParseResult` / `TimeParseResult` / `NumberParseResult` が実行可能な型定義になっていない**（B/G）
   - dataclass/`__init__` 未指定のまま `DateParseResult(...)` で生成しており破綻。
   - 修正方針: 3クラスを `@dataclass(frozen=True)` で確定。
3. **symlink拒否ロジックが要件を満たさない**（F/G）
   - `resolve(strict=True)` 後に `lstat` しても「入力経路上のsymlink」を検出できない。
   - 修正方針: `resolve` 前の元パス経路を `lstat` 検査し、その後 `resolved` の配下判定を行う2段階構造に変更。
4. **テンプレートPII混入防止仕様が破綻しうる**（F/G）
   - 「JSON全文字列走査 + `FORBIDDEN_TEMPLATE_VALUE_COLUMNS`」はキー名までヒットし、誤検知/漏れの両方が起きる。
   - 修正方針: 文字列走査を廃止し、`payload` の許可キー/値型を構造検証（ホワイトリスト）で固定する。

### Major 指摘
1. Pythonバージョンが固定されていない（`3.10+` は広すぎる） — `3.11.x` に固定。
2. 依存ゼロ方針と pytest 前提が衝突 — `unittest` を基本とし、pytest は任意扱いに整合させる。
3. CSV拡張子の扱いが設計書と不整合（`glob("*.csv")` と `suffix.lower()==".csv"` 受理の混在） — `suffix.lower()==".csv"` 受理、他は warning skip に一本化。
4. エラーカテゴリ出力規約と実装例が一致していない（`class名→lower()` では `rowcountmismatch` 等規約外） — 例外クラス→カテゴリ文字列の明示マップを実装。
5. E2E/単体テストに必須異常系が不足（空CSV、symlink入力拒否、`--allow-external-output` ガード） — 最低3ケースを追加。
6. 擬似コードの `...` が残り、Code-ready粒度が不足（`_assign_uniquely`、`BillingReportGenerator.generate`） — 引数・戻り値・副作用を固定。

### Minor 指摘
1. `KeyboardInterrupt=130` が終了コード表に未記載 — 表へ追記。
2. `FORBIDDEN_TEMPLATE_VALUE_COLUMNS` は命名が誤解を招く — `PII_VALUE_FIELDS_DENYLIST` 等に改名推奨。
3. `detect_dialect(sample_text)` の sample 取得量が未定義 — `先頭N行/全体` を固定。

### 良かった点
- 設計書のモジュール分割・責務分離はほぼ維持できている。
- `drop/keep/fail` と `dry-run` 優先順位、sidecar列固定など運用で揉めやすい点が明文化されている。
- PII適用範囲（stdout/stderrのみ）と出力先制限の意図は明確で、デモ用途に合っている。

### このラウンドでの対応
- Critical 全4件: **対応**
  - §4.3 `NormalizedCell` に `review_reason: str | None` を追加し、`ReviewCollector.collect` が `reason` を伝搬できるようにした。
  - §5.10–5.12 `DateParseResult` / `TimeParseResult` / `NumberParseResult` を `@dataclass(frozen=True)` で正式定義。
  - §6.9 `_guard_input_path` を2段階構造に変更（元パス経路の各要素を `lstat` → その後 `resolve` して samples 配下判定）。
  - §4.1 / §6.10 テンプレート保存を構造ホワイトリスト検証に置換（全文字列走査を廃止、`PII_VALUE_FIELDS_DENYLIST` と `ALLOWED_TEMPLATE_KEYS` を導入）。
- Major: **6件中 5件対応**
  - §1.3 / §2.1 Python を `3.11.x` に固定。
  - §2.2 / §10.1 テスト依存の衝突解消（標準ライブラリ `unittest` を基本、pytest 使用時は README で任意 dev 扱いと明記）。
  - §6.11（新設） 拡張子判定を `suffix.lower()==".csv"` 受理 / 他は warning skip に一本化、§8.1 の「拡張子違反」記述を修正。
  - §8.3 例外クラス→カテゴリ文字列の明示マップ（`_CATEGORY_BY_EXC`）を実装例に追加。
  - §10.3 異常系テストに「空CSV」「symlink入力拒否」「`--allow-external-output` 未指定時の外部出力拒否」の3ケース追加。
  - 見送り: `_assign_uniquely` / `BillingReportGenerator.generate` の完全擬似コード化 — 引数・戻り値・副作用の宣言は補強したが、内部ステップ完全記述はセミナーデモ用途では過剰と判断しPhase5実装時の裁量に委ねる（MAY降格）。
- Minor: **3件中 2件対応**
  - §7.3 終了コード表に `130` (`KeyboardInterrupt`) を追記。
  - §4.1 `FORBIDDEN_TEMPLATE_VALUE_COLUMNS` を `PII_VALUE_FIELDS_DENYLIST` に改名。
  - 見送り: `detect_dialect` の sample 取得量固定 — §5.4 で「先頭8KiBまたはファイル全体のうち小さい方」を注記として追加済（最小実装では Sniffer デフォルトに委ねる）。

---

## ラウンド2 (2026-04-23)

### 総合評価
**C** — R1と同格。R1で解消した「型/symlink/PII」系の骨格的欠陥は残っていないが、新たに `convert` の単発/バッチ分岐未確定、出力ガードの leaf 非存在許容の欠落、例外契約の不閉鎖、`keep` 出力契約（`__needs_review` 列 vs sidecar）と要件書の不一致が判明。Phase5 着手前に最後の詰めが必要。

### Critical 指摘
1. **`convert --input-dir` 分岐未定義**（`ConvertFlow.run` が `args.input` 固定で `BatchRunner` に到達不能）
2. **`_guard_output_path` が入力ガードの `lstat` 存在必須ロジックを転用すると新規出力を常に拒否**する。
3. **例外契約が閉じていない** — `TimesheetLoader.load` の `OSError`、`TemplateStore.load` の `FileNotFoundError` が `main()` の `DemoError` 一元キャッチに届かない。
4. **`keep` 出力契約が要件書 M6/M8 と不一致** — 要件は本体 CSV に `__needs_review` 列必須、仕様は sidecar のみ。

### Major 指摘
1. `FailPolicyHalt` が例外階層と `halted=True` 戻り値の2系統に割れていた。
2. `CleanupFlow` が §5 公開 API 一覧に欠落。
3. `HeaderInferencer._assign_uniquely` が `...` のまま。
4. `BillingReportGenerator().generate(...)` 呼び出しの引数がプレースホルダ。
5. `BatchRunner` の列挙方法と「非CSV warning skip」が単一パスでは両立しにくい。
6. `--mapping-file` の YAML 可否が要件書 §4.2 S1 と仕様書で不一致。

### Minor 指摘
1. ConvertFlow の参照節が §6.7 のまま（実体は §6.8）。
2. `unittest` 既定方針とサンプルコードの `pytest.raises` 記法が未整合。

### このラウンドでの対応
- Critical 全4件: **対応**
  - §6.8 `ConvertFlow.run` 冒頭に `args.input_dir` 分岐を追加し、`BatchRunner.run(input_dir, output_dir, args)` に委譲＋戻り値をそのまま終了コードとする規約を明文化。
  - §6.9 直後に `_guard_output_path` の完全擬似コードを追加（親ディレクトリのみ lstat 存在必須、leaf は非存在許容。resolve は parent に対して行い leaf 名を付け直して配下判定）。
  - 例外契約を `DemoError` 系で閉じる規約を §5.5（`TimesheetLoader.load`）と §5.19（`TemplateStore.load`）に明記。素の `OSError` / `FileNotFoundError` は内部で `InputValidationError` にラップ。加えて §8.3 `main()` に最終セーフティネット（`except (FileNotFoundError, OSError)`）を追加し、取りこぼしても §7.3 の終了コード 1 を保証。
  - §4.6 を「本体 CSV に `__needs_review` 列を追加 + sidecar 併用」に改訂。§5.17 `TimesheetWriter.write` に `policy` 引数を追加し、keep 時のみ 8 列目を書き出す契約を確定。§6.8 の writer 呼び出し側も更新。
- Major: **6件中 5件対応**
  - §5.1 `FailPolicyHalt` を例外階層から削除し、§8.1 表直下に「戻り値規約（`PolicyOutcome.halted=True`）で処理する」旨を明記。§7.3 終了コード表と §8.3 `_CATEGORY_BY_EXC` も整合化。
  - §5.23b に `CleanupFlow.run` を追加（シグネチャ・戻り値・例外契約）。
  - §5.24 `BatchRunner.run` を 2 パス方式に書き直し、全ファイル列挙 → 非CSV warning skip → CSV のみ処理対象の順序で記述。
  - §6.8 `ConvertFlow` 内の `BillingReportGenerator().generate(...)` 呼び出しを full kwargs に置換（halted 経路・通常経路の両方）。
  - 付録 C.1 に要件書 `:90` の YAML 記述を「仕様書を正として JSON 限定に読み替え、要件書次回改訂時に文面修正」と明記。仕様書・設計書・要件書の3文書間の最終解消トリガーを §4.5 / §5.20 / 付録 C.1 に固定。
  - 見送り: `_assign_uniquely` の完全擬似コード化 — R1 と同じ判断で、引数・戻り値・タイブレーク優先度・閾値判定規則までは §6.2 で宣言済み。セミナーデモ用途では内部ステップの完全擬似コード化は過剰と判断し Phase5 実装時の裁量に委ねる（R1 で MAY降格済、R2 再指摘に対し方針継続）。
- Minor: **2件中 2件対応**
  - §5.22 の参照節を `§6.7` → `§6.8` に修正。
  - §10.1 に `unittest.TestCase` ベースでの書き換え対応表（`assert x == y` → `self.assertEqual(...)`、`with pytest.raises` → `with self.assertRaises`、`tmp_path` → `tempfile.TemporaryDirectory()`）を追加し、§10.3 のサンプル記法と実装の橋渡しを明示。

---

## ラウンド3 (2026-04-23) ※最終

### 総合評価
**B（条件付きGo）** — R1/R2 の反映は高水準、実装骨格はほぼそのまま着手可能。ただし仕様矛盾1件（文字コード）とセキュリティ保証の過大表現1件（PII値検証）は Phase5 前に潰すべき、との判定。推移 **C（R1）→ C（R2）→ B（R3）** で実装着手可能水準に到達。

### Critical 指摘
1. **文字コード仕様が自己矛盾**: `detect_encoding()` が BOM 優先で `utf-8-sig` 即決しているが、サンプル/テストが「CP932 + BOM」を前提化しており誤判定しうる。
2. **PII保存禁止の保証が不十分**: `TemplateStore` の構造ホワイトリストだけでは `header_mapping[].source` や `source_hint` の値側に PII が混入しうる（許可キー内に値が入る）。

### Major 指摘
1. **CLI契約が不整合**: `--output` 既定値 `out/<basename>.csv` が表にあるが parser 定義に default 未設定。`--input-dir` との併用禁止も仕様記載のみで強制ロジック未定義。
2. **near-Python の未定義変数**: `report_path` / `sidecar_path` の決定ロジックが §6.8 に無く、実装者依存。
3. **バッチ時の出力先ガードが弱い**: `_guard_output_path` が単発中心で、`--input-dir` + `--output-dir` の安全制約が明文化不足。
4. **数値制約が不足**: `parse_wage` / `parse_minutes` が負値を許容しうる。

### Minor 指摘
1. §6.11 と §6.10 の順序逆転を修正（参照しやすさ改善）。
2. 依存一覧の `codecs` は現アルゴリズムで未使用なので削除候補。
3. Python 固定を `3.11.x` ではなく `3.11.9` など patch まで固定すると再現性が上がる。

### このラウンドでの対応
- Critical 全2件: **対応**
  - §5.3 / §6.1 文字コード判定を「BOM 検出後も `utf-8-sig` strict decode、失敗時は CP932 フォールバック」に変更し、fixture 方針も §6.1 末尾に明記。実装者が fixture を作るときに BOM + CP932 本体を誤判定しないことが保証される形に仕様を一本化。
  - §6.10 テンプレート保存の PII 防御に「構造検証 + 値検証」の二段構えを導入。`_HEADER_VALUE_REJECT_PATTERNS`（純数値・金額・日付・時刻）と長さ上限 64 で `header_mapping[].source` / `source_hint` がデータ値になっていないかをチェックし、通過時のみ `TemplateSchemaError` を回避する仕様に確定。§4.1 の `PII_VALUE_FIELDS_DENYLIST` は従来どおり防御的ラベルとして残す。
- Major 全4件: **対応**
  - §5.22 / §6.8 / §6.13 新設: `ConvertFlow._validate_convert_args` を追加し、`--input-dir` + `--output` 併用時 `InputValidationError`、`--input` + `--output` 未指定時は `out/<stem>.csv` を補完。§6.8 の run 冒頭 (Step 0a) で呼び出す順序を疑似コードで固定。
  - §6.12 新設: `output_path` / `report_path` / `sidecar_path` の決定規約を単発・バッチ両方について表で固定。`_resolve_paths(args) -> tuple[Path, Path, Path]` を §5.22 の ConvertFlow 仕様に追加し、§6.8 Step 3b で呼ぶ位置まで明示。命名衝突は「上書き、`cleanup` か手動削除で事前整理」に確定。
  - §5.24 / §6.9 末尾: BatchRunner 冒頭で `_guard_output_dir_for_batch(output_dir, allow_external)` を 1 回実行する規約を追加。出力先ディレクトリの経路 symlink 禁止 + `out/` 配下制約を単発と同強度で適用。未存在ディレクトリは parent resolve + leaf 追加で `out/` 配下判定。
  - §4.2 / §6.5 / §5.12: `parse_wage` / `parse_minutes` の返り値に `>= 0` 制約を追加。負値は `is_valid=False` で reason は「時給が負値」「休憩分が負値」。上限は設けず（将来拡張のため）。列制約表も「整数」→「`>=0` の整数」に更新。
- Minor 全3件: **対応**
  - §6.11 を §6.10 の前から §6.10 の後ろへ移動し、参照順を自然化。
  - §2.2 依存一覧から `codecs` を削除（`detect_encoding` は `bytes.decode()` のみで完結するため未使用）。
  - §1.3 / §2.1 Python バージョンを `3.11.x` → **`3.11.9`** に patch 桁まで固定。pyenv `.python-version` 記載と README 表示の 3 箇所で統一する運用も明文化。

---

## 最終残論点

R3 最終ラウンド完了時点で、仕様書に残る論点は下記 3 件。いずれも **Phase5 着手を阻害しない** 軽微事項として意図的に見送ったもの。

1. **`_assign_uniquely` の内部ステップ完全擬似コード化（MAY 降格継続）**
   - R1 / R2 / R3 を通じて「引数・戻り値・タイブレーク優先度・閾値判定は §6.2 で宣言済」で実装着手には十分と判断。セミナーデモ用途では内部フロー完全記述は過剰。Phase5 実装時に必要なら追記する。
2. **`BillingReportGenerator.generate` 内部の完全擬似コード化（MAY 降格継続）**
   - シグネチャ・呼び出し規約・テンプレート（§4.7）は確定。内部の Markdown/CSV 書き出し手順は実装者裁量で十分。
3. **要件書 `01_requirements.md:90` の `--mapping-file <yaml>` 記述の正本修正**
   - 本仕様書 §4.5 / §5.20 / 付録 C.1 で「JSON 限定」に読み替え確定済。要件書本体の文面修正は「次回要件書改訂時」に合わせて実施する運用で合意済（Phase5 実装自体には影響なし）。

### Phase5 着手可否
**可**。R3 指摘の Critical / Major は全て対応完了、Minor も全て対応。残論点 3 件はすべて MAY 降格・運用合意済で、実装着手には影響しない。セミナー実施日までの工数を考えると「十分実用的」の水準に到達。

---
