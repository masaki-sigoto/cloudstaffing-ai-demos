# 設計書レビュー履歴ログ

対象ドキュメント: `02_design.md`（CSV加工の完全自動化・勤怠CSV自動整形デモ）

---

## ラウンド1（Codex、2026-04-23）

### 総合評価
**C** — 要件トレースは丁寧だが、MUST違反につながる設計不整合が複数あり。特に `M2`（文字コード判定の範囲）、`M8 keep`（要確認セルの原値保持）、`M7 fail-fast`（出力前検証保証）はこのままだと要件未達。Phase4前に仕様の矛盾を先に潰すべき。

### Critical 指摘
1. **文字コード判定が要件と不一致**（§7.1 `read_bytes(limit=1MB)`）
   - 要件§5どおり「全バイトで UTF-8 strict → CP932 strict」を実施。1MB先読みは性能最適化としても、判定確定ロジックには使わない。
2. **`--error-policy keep` の仕様未充足**（§7.6 `keep` 分岐、§3.4 `NormalizedResult`）
   - 要確認セルは「正規化値」ではなく「原値を保持」するデータモデルに変更（`normalized_value` と `raw_value` の両持ち、keep時にreviewセルのみraw採用）。
3. **fail-fast保証の設計が内部矛盾**（§2.3 step10 書き出し後検証 vs §7.5 書き出し前検証、かつ `assert` 使用）
   - 検証順序を一本化し「`RowCountValidator` → 成功時のみ writer/report」。`assert` ではなく明示例外で判定。

### Major 指摘
1. ヘッダーマッピングの一意性制約が未定義（§7.2） — 1入力列→複数canonical割当不可を明文化、競合時は needs_review。
2. dry-run時のファイル非生成が設計で担保されていない（§2.3 step8, §6.1.1） — Flow入口で共通ガード。
3. `--mapping-file` の YAML対応が実装リスク高い（§3.1） — JSON限定に寄せる or 厳密サブセット固定。
4. 「実データ投入禁止」が運用依存（§9.3） — `--allow-non-sample-input` 明示必須の技術的ガード追加。
5. 最小実装方針に対して分割がやや過剰（§3.1） — Phase4ではコア収束、MAYは後置き。

### Minor 指摘
1. `--continue-on-error` の「既定on」をflagで表すのは誤解を生む（§6.1.1） — `--fail-fast` のみ公開、未指定=継続をデフォルトに一本化。
2. `BillingReportGenerator` は現スコープに対して将来文脈寄り命名（§3.3, C.7） — 現段は `ReviewReportGenerator` 等。
3. `mask_wage` が「桁」ではなく文字長マスク（§7.7） — 要件文言に合わせ仕様固定。

### 良かった点
- 要件IDと設計章の対応表があり、トレーサビリティの土台が強い。
- `PIIMasker` を出力経路から分離（M9担保）。
- `ReviewCollector` と `ErrorPolicyApplier` の分離（M8マトリクス実装見通し良好）。
- データモデル（`ReviewCell`, `Counters`）明示でテスト仕様に落とし込みやすい。

### このラウンドでの対応
- Critical 全3件: **対応**
  - §7.1 文字コード判定を全バイト判定に修正、1MBは非判定の性能メモに再定義。
  - §3.4/§7.6 `NormalizedResult`に`raw_value`両持ち追加、keep時はreviewセルの原値を採用する仕様を明記。
  - §2.3 step順を「カウンタ確定 → 検証成功時のみ write/report」に並び替え、§7.5 `assert`を明示例外（`RowCountMismatchError`）に置換。
- Major: **5件中 4件対応**
  - §7.2 一意性制約（1入力列→1canonical、競合時needs_review）明文化。
  - §2.3/§6.1.1 dry-run共通ガード（Flow入口で書き込み全停止）明記。
  - §3.1/§6.1.2 `--mapping-file` をJSON限定に縮小。
  - §9.3/§6.1.1 `--allow-non-sample-input` 明示必須ガード追加。
  - 見送り: モジュール粒度の再整理 — Phase4時点の実装リファクタで吸収すべき範疇とし、設計書上は責務分離を維持。
- Minor: **3件中 2件対応**
  - §6.1.1 `--continue-on-error` を削除、`--fail-fast` のみに一本化。
  - §7.7 `mask_wage` を「全面 `*` 化」に仕様固定（桁数も漏らさない）。
  - 見送り: `BillingReportGenerator` 改名 — 付録C.7で意図的命名の理由を明記済。デモでの業務文脈訴求を優先しMAY降格。

---

## ラウンド2 (2026-04-23)

### 総合評価
**C** — R1の Critical 3件（文字コード・keep原値保持・fail-fast順序）は解消されたが、反映の副作用として新しい仕様矛盾（`keep` 時の `__needs_review` 列がcanonical 7列と衝突、`fail` 時のレポート出力条件の章間不整合、M9ガードのsymlink迂回可能性）が発生。R1比で「骨格は合格、実装開始手前」の水準へ到達。

### Critical 指摘
1. **`keep` で `__needs_review` 列を CSV に追加（§7.6 vs §5.1）** — canonical 7列と衝突し M6 仕様違反。
2. **`fail` 時のレポート出力が自己矛盾（§4.3 vs §2.3/§7.5）** — 片や「report出力」、片や「validate成功時のみreport」。
3. **実データ禁止・出力先制限のガードが迂回可能（§9.2/§9.3）** — `--output` 外部指定が即許可、symlink考慮が不明。

### Major 指摘
1. `--mapping-file` のJSON/YAML表記不一致（§5.4 vs §3.1/§6.1.2）。
2. `--continue-on-error` 廃止済みだが §8.4 に残存。
3. 「全列未マッピングでも続行」は失敗を成功に見せる（§4.3）。REQUIRED列未確定はFatalへ。
4. 行IDの設計不足。`row_no(row)` が擬似コード依存（§3.4, §7.6）。
5. CLIオプションの相互排他ルール不足（`--input-dir` と `--output` 等）。

### Minor 指摘
1. `DialectDetector` の Sniffer失敗時フォールバック規則が未定義。
2. 拡張子判定が `.csv` 固定で大文字扱い不明。
3. `mask_name` の先頭1文字露出は短名で識別性高い。

### 良かった点
- 要件ID→設計セクションの対応表でトレーサビリティが引き続き良好。
- `ErrorPolicyApplier` と `RowCountValidator` の分離、fail-fastを書き出し前に置く判断が妥当。
- `NormalizedCell` で raw/normalized を両持ちにした点が M8 `keep` 要件に対して強い。
- 非サンプル入力ガードをフロー入口に置く方針が運用依存を減らす良い設計。

### このラウンドでの対応
- Critical 全3件: **対応**
  - §7.6 `keep` 出力から `__needs_review` 列を削除、canonical 7列固定を維持。要確認フラグはsidecar（`<basename>_needs_review.csv`）＋レポートに退避（§6.3 追記）。
  - §2.3 step9/§4.3/§7.5 で「`fail`+`review>0` は writer のみ停止、report は許可」「`RowCountMismatchError` は writer/report とも停止」を章間統一。
  - §9.2/§9.3 で `Path.resolve(strict=True)` による実パス正規化・symlink 拒否・外部出力は `--allow-external-output` フラグ明示必須を追加。CLI表にもフラグ追加。
- Major 全5件: **対応**
  - §5.4 `mappings/` の説明を「JSON 限定」に統一（§3.1/§6.1.2 と整合）。
  - §8.4 の `--continue-on-error` 言及を `--fail-fast` 前提に書き換え。
  - §4.3 の「全列未マッピングでも続行し空ヘッダー出力」を廃止、REQUIRED列未確定は Fatal（exit=1）に変更。§8.4 回復可能/不可能表にも反映。
  - §3.4 で `NormalizedRow{row_no, cells}` を新設し、§7.6 擬似コードを `row.row_no` / `row.cells` 参照に書き換え。`row_no(row)` の擬似関数依存を解消。
  - §6.1.1 にCLI無効組合せ表を追加（`--input-dir` と `--output` はエラー等）。argparse排他グループ前提。
- Minor: **2件対応／1件見送り**
  - §3.1 `DialectDetector` 行に Sniffer失敗時フォールバック順（`,` → `\t` → `;`、`\r\n` → `\n`）を明記。
  - §6.3 読み込み対象の拡張子判定を「大文字小文字非依存」と明記（`.CSV`, `.Csv` も受理）。
  - 見送り: `mask_name` 既定の `***` 固定化 — 先頭1文字露出のデモ視認性を優先。設定化は将来拡張扱いで技術仕様書側判断に委譲。

---

## ラウンド3 (2026-04-23) ※最終

### 総合評価
**B（条件付きでPhase4進行可）** — R1(C) → R2(C) → R3(B) と着実に前進。R2で発生した副作用（sidecar衝突、fail時レポート矛盾、symlink迂回可能性）はすべて解消済み。R3で新たに指摘された副作用は「ガード判定の誤検知リスク」と「異常系の分類不整合」の2系統で、いずれも仕様文書レベルの整合作業で解消可能な範疇。Critical を潰せば Phase4 着手可能と Codex 側も明言。

### Critical 指摘
1. **§9.3 symlink/実パス判定ロジックが実運用入力を誤拒否する可能性** — 「resolve前後で実パスが異なる場合は拒否」は相対パス指定でも差分が出るため誤検知しやすい。
2. **§8.1/§4.3/§8.4 の異常系分類不整合** — 「全列未マッピング」「空CSV」をR2で Warning 継続扱いにしたが、§4.3/§8.4 では REQUIRED 未確定は Fatal と明記されており章間矛盾。

### Major 指摘
1. §7.5 `fail` ポリシー時の件数照合が `review_rows>0` チェックだけで、`input/output/dropped` の不整合を検知できない。
2. §3.4/§5.2/§6.3 の `row_no` 語義が「入力ファイル行番号」と「出力CSV上の行番号」で揺れており、sidecar とログで追跡不能に陥る可能性。
3. §9.3 の `--input-dir` 配下 CSV が外部実体への symlink だった場合、ディレクトリ単位判定だけでは迂回可能。

### Minor 指摘
1. §2.3/§7.5 で `--dry-run` と `fail+review時レポート出力` の優先順位が曖昧。
2. §10.2 バッチ処理の入力順序がOS依存のままだとデモ再現性が落ちる。

### このラウンドでの対応
- Critical 全2件: **対応**
  - §9.3 を「`resolve(strict=True)` 後の絶対パスと `samples/` 実パスを `is_relative_to` で比較（文字列差分比較は廃止）」「各パス要素を `Path.lstat()` でリンク判定し symlink なら拒否」に再設計。バッチ時は各ファイルに同ガードを再適用する旨を追記。
  - §8.1 の分類表から「全列未マッピング / 空CSV」を Warning 枠から削除し Fatal 枠に移設。§4.3 の分岐説明にも「全列未マッピング / 空CSV は REQUIRED 未確定の特殊形として Fatal」を明記。`--allow-empty` は現スコープ非提供と宣言（設計原則で統一）。
- Major 全3件: **対応**
  - §7.5 の `fail` 分岐に「`review_rows==0` でも `input==output` かつ `dropped==0` を検証」する件数整合チェックを追加。`RowCountMismatchError` を明示送出。
  - §3.4/§5.2/§6.3 で `row_no` を `source_row_no`（入力）と `output_row_no`（出力）に分離定義。sidecar 列を `output_row_no, source_row_no, has_review, review_columns` の4列に確定。§7.6 擬似コードも `row.source_row_no` 表記に更新し、`ReviewCell` 定義を `source_row_no` に改名。
  - §9.3 に「`BatchRunner` が列挙した `*.csv` の各ファイルに対して同ガードを再適用」を MUST として明記（ディレクトリ判定のみの迂回を防止）。
- Minor 全2件: **対応**
  - §2.3 step9 に「`--dry-run` は全書き出し停止を最優先、dry-run > fail-report」と明記。
  - §10.2 に「`BatchRunner` は `sorted()` によるコードポイント昇順でファイルを列挙する（MUST）」を追加。

### 判定
- R3 で指摘された Critical/Major/Minor は **すべて設計書内の整合作業で解消済み**。
- R3 で Codex が「Critical を潰せば次フェーズに進める状態」と明言しているため、**Phase4（技術仕様書作成・最小実装着手）進行可** と判断する。
- 本ラウンドを **最終レビュー** と位置付け、これ以降の細部チューニングは技術仕様書／実装PR側で吸収する方針。

---

## 最終残論点

以下は R3 時点で意図的に残置した項目。Phase4 以降（技術仕様書または実装着手時）で確定／再評価する。

- **同義語辞書の完全エントリ**: §7.2 の辞書は抜粋。派遣業界語彙の網羅は技術仕様書で確定（編集距離しきい値 `0.80 / 0.60` も実運用サンプルでの再チューニング余地）。
- **`mask_name` の先頭1文字露出**: R2 で見送り済。短名（例: `王`）の識別性リスクは残存。セミナー視認性を優先し現状維持。将来設定化は技術仕様書判断に委譲。
- **`--allow-empty` フラグ**: R3 で現スコープ非提供と宣言。空CSV許容が必要なユースケースが出てきた時点で追加（既定は Fatal のまま据え置き）。
- **バッチ一部失敗時の exit=2 分岐**: §6.2 で MAY のまま。最小実装では MUST 部（全成功=0 / それ以外=非ゼロ）に絞る想定。
- **性能最適化（ストリーム判定・10万行処理）**: §7.1 の通り、判定ロジックは全バイト判定で固定し、最適化は技術仕様書で別途検討。
- **LLMベース HeaderInferencer 差替え**: §10.4 の将来拡張接続点として予約済。現フェーズでは `RuleBasedInferencer` のみ実装。

これらは「仕様の穴」ではなく「スコープ外に置いた設計上の選択」である旨を、技術仕様書フェーズに引き継ぐ。
