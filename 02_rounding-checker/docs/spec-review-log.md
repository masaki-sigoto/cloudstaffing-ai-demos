# Codex レビュー履歴: 技術仕様書（02_rounding-checker）

## ラウンド1 (2026-04-23)

### 総合評価
**B**
設計書との対応は全体として良く、Phase5 着手可能な粒度まで落ちていた。
ただし、**`--baseline` 解決仕様の自己矛盾**と**例外契約の不整合**があり、このまま実装すると exit code や比較結果が揺れる懸念があった。
R1 では Critical を先に潰し、デモ安定性（exit code 一貫性・再現性・PII 防御の抜け穴封鎖）を優先して反映。

### Critical 指摘

- [x] 指摘1: `--baseline` の解決規則が自己矛盾（§7.3 と §10.2.7 最終行が不整合）
  - 修正方針: 「**数字文字列は常に index 優先**」に一本化。§6.11 を新設して `resolve_baseline` 擬似コード・決定記録を明示。§7.3 のオプション表（型を `str` に統一、参照先 §6.11 を追記）と §10.2.7 テスト表を整合させた。pseudocode（§6.5）にも注釈を追加。
- [x] 指摘2: `config_loader` の型バリデーションが不足し、想定外例外が exit 1 化する穴（§6.6）
  - 修正方針: §6.6 の `load_rule_from_dict` を書き換え、`clock_in`/`clock_out` の `isinstance(..., dict)` 検査、`break.minutes` の `int()` を `try/except (TypeError, ValueError)` で包む、`unit_minutes` の厳格 int 検査（`bool` 排除）を追加。すべて `ConfigValidationError`（exit 2）に正規化。方針ノートも追記。
- [x] 指摘3: `calc_pay` の例外契約が不一致（§5.5 は `PayrollError`、§6.3 は `ValueError`）
  - 修正方針: `PayrollError` に一本化。§5.5 docstring と §6.3 擬似コードの `ValueError` → `PayrollError` に置換。§8.1 / §8.2 にも exit 2 マッピングを明記。
- [x] 指摘4: 文字コード異常（CP932 / 混在）時の仕様未定義（§2.3, §8, §10）
  - 修正方針: §2.3 に扱い方を追加、§6.6（YAML）/§6.7（CSV）で `UnicodeDecodeError` を `ConfigValidationError`/`PunchValidationError` に正規化、§8.2 に exit code と推奨メッセージ、§10.2.12 に CP932 / Shift_JIS / 破損バイト列のテストケースを追加。

### Major 指摘

- [x] 指摘5: `--show-gross` のデータフローが弱い（§7.3, §5.10）
  - 修正方針: `ComparisonRow` に `gross_min` を**常時**追加（§4.7）。§4.5 JSON / §4.6 CSV スキーマを更新して `--show-gross` による列表示制御に統一。§6.5 擬似コードも `total_gross` 累積に修正。「formatter 側で gross を再計算してはならない」を明文化。
- [x] 指摘6: `explain()` の休憩値優先順位が不明確（§5.7）
  - 修正方針: §5.7 に「`break_min` は engine が確定した最終値」を明記。§5.9 `run_explain` で `effective_break = break_min_cli if not None else rule.break_minutes` を確定してから `explain()` へ渡す流れに固定。
- [x] 指摘7: 依存バージョンが下限指定のみで再現性が弱い（§2.1, §2.2）
  - 修正方針: §2.1 にデモ登壇機の **Python 3.10.14 固定**、§2.2 に PyYAML **6.0.1 固定**を追記。下限要件は維持しつつ実績バージョンを併記。
- [x] 指摘8: `DEMO_BUILD` 切替の運用ガードが弱い（§4.1）
  - 修正方針: `DEMO_BUILD` 環境変数判定を **`src/build_flags.py` の定数 `IS_DEMO_BUILD` 参照**に変更。環境変数での実行時上書き不可を §4.1 に明記。開発ビルドはファイル差し替えで切り替える運用を規定。
- [x] 指摘9: 行単位警告メッセージの粒度が粗い（HH:MM:SS 分岐が沈黙）（§6.8）
  - 修正方針: `parse_time` に `_TIME_WITH_SEC_RE` を追加し、秒付き入力時は `seconds are not supported (use 'HH:MM', got ...)` 専用メッセージを投げる。§10.2.3 テスト表の期待値を強化。

### Minor 指摘

- [x] 指摘10: `pytest` 前提なのに依存表に dev 依存記載がない（§2.2, §3, §10）
  - 修正方針: §2.2 依存表に `pytest >= 7.4`（dev 専用、デモ機検証は 7.4.4）を追加。
- [x] 指摘11: `generated_at` のタイムゾーン表現が未定義（§4.5）
  - 修正方針: JSON スキーマの例を `+09:00` 付きに更新。`datetime.now(tz=...)` による実装規約を追記、naive 時刻禁止を明記。
- [x] 指摘12: ログサマリ項目名が設計書の `processed_count/skipped_count` と揺れる（§9.1）
  - 修正方針: §9.1 / §9.2 の実行サマリを `processed_count / skipped_count / exit_code` に統一。設計 §10.1.1 と同一キーに揃えた。

### 良かった点

- 設計書→仕様書のトレーサビリティは高く、モジュール対応もほぼ崩れていない。
- 丸め・金額計算を整数演算で固定した点は、デモの説明可能性と再現性に効いている。
- PII 対策（allowlist + forbidden 列 + `--out` 制限 + デモビルド制約）は実装箇所まで具体化できている。

### このラウンドでの対応

- Critical 4件すべて対応（baseline 規則統一、`config_loader` 型検査、`calc_pay` 例外一本化、文字コード異常系）。
- Major 5件すべて対応（`ComparisonRow.gross_min` 常時保持、`explain` 責務分担、バージョン固定、`DEMO_BUILD` 定数化、`HH:MM:SS` 専用メッセージ）。
- Minor 3件すべて対応（pytest 依存明記、`generated_at` TZ 固定、ログキー統一）。
- 見送りは**なし**（R1 で指摘された12件はすべて反映）。PyYAML 採用方針・真理値表・金額計算式・警告条件の本質仕様は変更なし。

## ラウンド2 (2026-04-23)

### 総合評価
**B**
R1 で Critical/Major はかなり反映済みだが、exit code 設計を崩す例外正規化漏れ（I/O 系）と、成立しない文字コードテスト（ASCII のみ CP932 は UTF-8 合法）が残存。加えて `build_flags` 周りに仕様内矛盾が混入していた。R2 ではこれらを潰し、`gross<0` 反転の業務ルールも決めて警告文言・アルゴリズム・テストを揃えた。

### Critical 指摘

- [x] 指摘1: §10.2.12 の先頭ケースが技術的に成立しない（ASCII のみの CP932 は UTF-8 合法）
  - 修正方針: 全ケースで非 ASCII バイト列を含む `bytes` フィクスチャに再定義。`氏名`=`b"\x8e\x81\x96\xbc"` 等をヘッダ／行データに含める形に書き換え。実装ポイントに `Path.write_bytes` でのバイト列固定化ルールを追記。
- [x] 指摘2: ファイル I/O 例外の正規化漏れで exit 1 に落ちる穴（§5.2, §6.6, §6.7, §8.2）
  - 修正方針: §5.2 / §5.3 の docstring に `FileNotFoundError` / `PermissionError` / `IsADirectoryError` / `OSError` / `csv.Error` の正規化方針を明記。§6.6 `load_rule` / §6.7 `parse_punch_csv` の擬似コードに個別 `except` 節を追加し、全て `ConfigValidationError` / `PunchValidationError` に変換。行単位の `csv.Error` は `PunchRowError` 扱いで skip 継続に統一。

### Major 指摘

- [x] 指摘3: `build_flags.py` が仕様本文内で未整合（§4.1 vs §3）
  - 修正方針: §3 ディレクトリ構成に `build_flags.py` を追加。symlink 運用は廃止し、単一ファイル定数 + デモ前チェックリスト（`grep -n "^IS_DEMO_BUILD"` で目視確認）に簡素化。
- [x] 指摘4: 例外階層と擬似コードの乖離（§8.1 vs §6.7）
  - 修正方針: §6.7 `_validate_header` を `ForbiddenColumnError` / `ColumnNotAllowedError` のサブクラス送出に合わせた。必須列欠損は汎用 `PunchValidationError` のまま。§8.2 のマッピング表は既に個別行あり。
- [x] 指摘5: `DemoError` 統一方針と `ValueError` 送出の衝突（§6.1, §6.8）
  - 修正方針: §6.1 に方針ノートを追加し、`round_minutes` / `format_minutes` の `ValueError` は**契約違反検出用のみ**で main 到達経路では発生しないことを明文化。`parse_time` / `load_rule_from_dict` で先に `DemoError` 系に変換される前提を担保する。
- [x] 指摘6: 丸め後 `gross<0` の扱い未定義（§6.2, §6.4, §6.5）
  - 修正方針: §6.2 `round_punch` に方針ノート追加。§6.4 `compute_net` で専用 `[WARN] gross became negative after rounding ...` + 0 クランプを実装、休憩過大メッセージとの二重出力を防止。§6.5 `compare_rules` 側も同じルールで WARN + 0 加算。§10.2.8.1 に専用テストケース追加。
- [x] 指摘7: テスト一覧の不整合（§10.1 vs §3）
  - 修正方針: §3 ディレクトリ構成に `test_engine.py` を追加し、§10.1 の対象一覧と一致させた。

### Minor 指摘

- [x] 指摘8: 終了コード定義の文言が `validate` と噛み合わない（§7.6）
  - 修正方針: §7.6 に `validate` はスキーマ適合で exit 0 という例外規定を1行追加。
- [x] 指摘9: JSON 型表現が曖昧（§4.5 `rule_name: "string | [string]"`）
  - 修正方針: `string | list[string]` に明示化。サブコマンド別固定形（simulate/explain/validate=string、compare=list[string]）を §4.5 直下に追記。
- [x] 指摘10: `parse_punch_stdin` の UTF-8 強制手段が弱い
  - 修正方針: §5.3 に `sys.stdin.buffer.read()` → `bytes.decode("utf-8-sig")` による明示デコード方針を追記。ロケール依存テキストストリーム不使用を明文化。

### 良かった点

- compare の「行単位丸め合算」がアルゴリズム・テストで一貫。
- `break` 優先順位の責務分離（engine 確定→explainer 受領）が明快。
- 24:00 境界、baseline 解決、UTF-8 正規化が R1 で具体化済み。
- 出力スキーマと終了コード記述の密度が実装直前として高い。

### このラウンドでの対応

- Critical 2件すべて対応（文字コードテストの `bytes` フィクスチャ化、I/O 例外正規化）。
- Major 5件すべて対応（`build_flags` 整合、例外階層とサブクラス送出の一致、`ValueError` 契約明文化、`gross<0` 専用ルール、`test_engine.py` 追加）。
- Minor 3件すべて対応（validate exit 0 例外規定、`rule_name` サブコマンド別型固定、stdin UTF-8 明示デコード）。
- 見送りは**なし**。PyYAML 採用維持、要件・設計書との整合性を維持。

## ラウンド3 (2026-04-23) ※最終

### 総合評価

**B（条件付きで Phase5 着手可）**。
R1/R2 で Critical/Major の大宗は解消済みだが、トレーサビリティ宣言の事実不一致（「設計§3.1 と 1:1」記述と 3 モジュール追加の実態が食い違う）、再現性要件と `run_id`/`generated_at` の衝突、`emit_comparison` の `warnings` 不整合、CSV ヘッダ正規化ルール未定義という **仕様書内の矛盾 4 件** が残っていた。R3 ではこれらを最小編集で潰し、実用上「実装判断が割れる箇所」を排除した。評価推移は **R1: B → R2: B → R3: B**（着手可）だが、R3 で残っていたトレーサビリティ / 出力仕様の矛盾が消え、Phase5 での手戻り余地はほぼ無い状態にたどり着いた。

### Critical 指摘

- [x] 指摘1: 設計書との「1:1 対応」宣言が事実不一致（仕様書に `exceptions.py` / `logging_config.py` / `build_flags.py` が追加されている）
  - 修正方針: §1.1 トレーサビリティ文面を書き換え、**10 モジュールは設計§3.1 と 1:1、補助 3 モジュールは本仕様書で追加**と明示。§3 ディレクトリ構成の 3 行コメントに「（設計§3.1 対象外の補助モジュール）」を付記。付録 D トレーサビリティ表にも補助 3 モジュールの行を追加。設計書側は編集せず、仕様書側で差分承認文面を確定した。

### Major 指摘

- [x] 指摘2: 再現性要件（同入力→同出力）と `meta.run_id`（UUID）・`meta.generated_at`（現在時刻）が衝突
  - 修正方針: §7.1.1 共通オプションに `--deterministic` フラグを追加。§4.5 JSON スキーマ直下に「`--deterministic` 時は `run_id=000000000000` / `generated_at=1970-01-01T00:00:00+09:00` に固定」を明記。§9.7 を `make_run_metadata(deterministic)` 擬似コードに書き換え、`[INFO] summary` の `run_id` も連動させた。既定（未指定）では従来通り UUID4 + 現在時刻で、golden 比較・デモ録画再現時は `--deterministic` を必須運用に。
- [x] 指摘3: JSON スキーマの `warnings` キーと `emit_comparison()` / `run_compare()` シグネチャが不整合
  - 修正方針: §5.8 `compare_rules` の戻り値を `tuple[list[ComparisonRow], list[str]]` に変更。§5.9 `run_compare` も同じ戻り値に。§5.10 `emit_comparison` シグネチャに `warnings: list[str]` を追加し、JSON の §4.5 `warnings` キーへ流す責務を仕様化。§6.5 擬似コードに `warnings` リストを初期化→収集→返却する処理を追加し、`[WARN]` の stderr 出力と JSON 出力の源泉を一本化。
- [x] 指摘4: CSV ヘッダ検証（`strip().lower()` 正規化）と `_row_to_punch` のキー前提が未定義
  - 修正方針: §6.7 `_validate_header` の戻り値を `dict[str, str]`（raw→canonical マップ）に変更。`parse_punch_csv` で各行を canonical キー辞書に詰め替えてから `_row_to_punch` に渡すよう擬似コード更新。重複 canonical（`Clock_In` と `clock_in` の同時指定）は `PunchValidationError` で拒否する契約を追加。§10.2.4 テスト表にヘッダ揺らぎ正常系と重複異常系の 2 ケースを追加。

### Minor 指摘

- [x] 指摘5: `yaml.__version__` の `int()` 分解がプレリリース文字列で例外化する穴
  - 修正方針: §2.4 に `_parse_yaml_version` ヘルパを追加、各セグメントから数字プレフィクスのみ取り出す実装に変更。`6.0.1rc1` 等でも exit 1 に落ちない。
- [x] 指摘6: `name` / `description` の YAML 型検証が緩い（`str()` 暗黙変換で数値・dict を通す）
  - 修正方針: §6.6 `load_rule_from_dict` に `isinstance(..., str)` 検査を追加。非 str は `ConfigValidationError` に正規化し、スキーマ厳格性を合わせた。
- [ ] 指摘7: 依存バージョン固定が「運用上固定」にとどまり、依存宣言は範囲指定のまま
  - 対応: **見送り**。§2.2 直下のノートに「完全 pin は Phase5 のパッケージング決定時に `pyproject.toml` と合わせて決める」旨を追記し、最終残論点（下記）へ送った。Phase5 のタスクとして明示し、着手判断には影響しない扱い。

### 良かった点

- `compare` の行単位丸め合算、共通 `amount_rounding` / `break` の処理が一貫。
- 24:00 境界、`gross<0` 反転、文字コード異常、入力ソース排他、`--out` 制限が具体化され実装揺れが少ない。
- `DemoError` → exit 2、未捕捉 → exit 1 のマッピングが例外階層ごとに揃っている。

### このラウンドでの対応

- Critical 1件すべて対応（トレーサビリティ宣言と実態を整合）。
- Major 3件すべて対応（`--deterministic` 追加、compare warnings の一貫化、CSV ヘッダ正規化ルール確定）。
- Minor 2件対応・1件見送り（依存完全 pin は Phase5 のパッケージング決定で再検討。最終残論点へ送付）。
- 仕様本質（真理値表、金額計算式、PyYAML 採用、例外階層、compare 行単位丸め、24:00 境界、PII allowlist）は変更なし。

## 最終残論点

R3 までで Phase5 着手可能。残る決定は Phase5 側で処理する前提で、本仕様書では意図的にスコープ外にした項目のみを記す。

| # | 項目 | 扱い | 理由 |
|---|---|---|---|
| 1 | 依存ライブラリの完全 pin（`PyYAML==6.0.1`, `pytest==7.4.4` 等） | Phase5 のパッケージング決定（`pyproject.toml` / `requirements.txt`）時に確定 | §1.3 でパッケージングは本仕様書スコープ外と宣言。現状は範囲指定 + 登壇機の実績バージョン併記で運用担保（R3 Minor 3）。 |
| 2 | ANSI 色の具体 RGB 値 | Phase5 実装時 | §1.3 既定のカバー外。`[WARN]=33m` / `[ERROR]=31m` / `[INFO]=36m` のコード割り当てのみ固定。 |
| 3 | `samples/` 最終バイト列（YAML / CSV 本体） | Phase5 実装時 | 付録 A / B のテンプレート確定済み。行数・匿名 ID は実装時に `samples/` へ作成。 |
| 4 | `overtime` SHOULD 機能の本実装 | 将来拡張（本デモ対象外） | 要件書 SHOULD。現状は WARN で読み捨て、`advanced/` 配下サンプルのみ残置。 |
| 5 | `pytest` 自動化・CI 統合 | Phase5 以降 | §C.9 で CI 整備は Phase5 範囲外と確認済み。手元 `pytest tests/` で通るレベルは Phase5 で達成。 |
| 6 | 仕様書・要件書・設計書の最終バージョン昇格（v1.0） | Phase5 実装完了時 | 現状 v0.1（初版）。実装で不整合が露見しない確認後に昇格する運用。 |

> **Phase5 着手判定**: Codex R3 で指摘された Critical / Major は全件対応済み。残 Minor 1 件は Phase5 のパッケージング議論とセットで処理する設計上の先送りのため、実装着手をブロックしない。要件定義書 v0.4・設計書 v0.1・本仕様書 v0.1 の 3 点で Phase5 に進んでよい。
