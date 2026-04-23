# Codex レビュー履歴: 技術仕様書

## ラウンド1 (2026-04-23)

### 総合評価
**C**
構成・粒度は実装直前として十分だが、**再開導線とPII制御に実害級の欠陥**があり、このまま Phase5 に入ると要件 M-11/M-13 と設計 §9.1.1 に反する実装が高確率で出る。決定表・PATTERN_RULES の単一ソース化とモジュール分離は維持できているため、Critical/Major を潰せば実装着手可能な水準に戻せる。

### Critical 指摘
- **CS-R1-1. 復元導線が設計違反（§8.6 `init` / `onResume`）**
  - `hasSavedSession()` が true なら起動直後に `btn-resume` が表示され、`保存する` 明示前に `load()` 実行可能。設計 §9.1.1「2アクション明示（保存する + 続きから再開）」を満たしていない。
  - 修正方針: `persist=local` 選択時にのみ `btn-resume` を表示・活性化。`onResume` 冒頭で `persistMode==='local'` を必須ガード。
- **CS-R1-2. 再開後に保存が止まるバグ（§8.2 `save` / §8.6 `onResume`）**
  - `load()` 復元後も `persistMode` が `'none'` のままになり得るため、その後 `Persist.save()` が全て no-op になる。
  - 修正方針: `onResume` で `State.get().persistMode='local'` を明示セット。保存ペイロードにも `persistMode` を含めて復元時に整合させる。
- **CS-R1-3. 致命エラー時の停止仕様が未実装（§6.4 / §9.1 / §8.6 `init`）**
  - 仕様上「設定エラー時は開始ボタン disabled」だが、`validateConfig()` の戻り値を `init` で使っておらず起動継続する。
  - 修正方針: `init` 冒頭で `if (!validateConfig()) { disableStartButtons(); return; }` を必須化。
- **CS-R1-4. 営業メモ印字条件が PII 漏えい寄り（§10.3 / §11.3）**
  - 「匿名化 OFF **または** 営業メモ印字 ON」で印字という記述は、匿名化解除だけでメモが出る解釈を許し「デフォルト非印字」と衝突。
  - 修正方針: 真理値表を固定し、`printSalesMemo===true` を唯一の印字条件とする（匿名化トグルはマスキング可否のみ担当）。
- **CS-R1-5. PII スキーマ不整合（§4.3 / §11.3）**
  - 匿名化対象に「担当者名」を含める記述があるのに `pii` に項目がない。実装で必ずズレる。
  - 修正方針: `pii: { companyName, contactName, date }` に統一し、画面・印刷・匿名化処理・コピー除外対象を同一定義に寄せる。

### Major 指摘
- **MS-R1-1. 設計とのトレーサビリティが曖昧（§6.2）**
  - `PATTERN_RULES` の優先順（3:D,4:B,5:A）が設計書例（3:B,4:A,5:D）と不一致で、変更意図の記録がない。
  - 修正方針: どちらを正とするか決定し、根拠を「決定記録」に追記。
- **MS-R1-2. ルール説明文と実ロジックが不一致（§6.2 `ruleLabel` vs §8.4 `calcCFull`）**
  - E の `ruleLabel` は「Q17未整備/一部のみ」を含むが、実装は `Q17=PART` で C=2 にしか上がらず E 発火しない。説明と判定が食い違う。
  - 修正方針: `ruleLabel` か `calcCFull` のどちらかを正規化（PART は C=2、C=3 発火は NOT_READY/UNKNOWN のみとして文言を修正）。
- **MS-R1-3. `printDetailModel` が型として固定されていない（§10.3 言及のみ）**
  - 設計で固定した `header/answers/matchedRule/checkList/...` の実装型定義が不足し、出力列ブレの余地が残る。
  - 修正方針: JSDoc typedef を追加し、`Render.toPrint('detail')` の入出力契約を明示。
- **MS-R1-4. 例外体系/終了コードの扱いが未宣言**
  - CLI ではないので終了コードは不要だが、仕様上「N/A」を明記しないとレビュー観点で曖昧。
  - 修正方針: §9 に「本プロジェクトはブラウザ実行のため終了コード定義なし」を明記。
- **MS-R1-5. テストが重大経路を取り切れていない**
  - `resume表示条件`, `resume時persistMode`, `validateConfig失敗時start不可`, `salesMemo印字真理値表` のテストが欠落。
  - 修正方針: §13.2 に UI テスト 4 本追加。
- **MS-R1-6. 型契約が不足**
  - `Judge.evaluate()` 戻り値、`Flow.progress()`、`Persist.load()` 適用後の State 完全性が JSDoc で未固定。
  - 修正方針: typedef を追加し、`Object.assign` で壊れない最小必須キーを定義。

### Minor 指摘
- **mS-R1-1.** §5.1 が「`QUESTIONS` 配列」と書きつつ実体は辞書オブジェクト。用語統一したい。
- **mS-R1-2.** DOM骨格の `progressbar` 初期 `aria-valuemax="7"` はフル版可変仕様と齟齬。初期値固定を避ける説明を追加。
- **mS-R1-3.** `Persist.load()` の `appVersion` 非互換時ポリシー（破棄/移行）が未定義。`v1 固定` として明記推奨。
- **mS-R1-4.** `buildReasonHighlights()` の `axis:'EXT'` は result スキーマ例と型集合がズレるため、列挙値に追加するか別フィールド化。
- **mS-R1-5.** `State.applySnapshot()` が浅いマージ前提。`ui` や将来拡張キーの破損防止ルールを1行で定義したい。

### 良かった点（R1レビュアー指摘）
- モジュール責務（AppCore/Flow/Judge/Render/Persist/State）が明確で、実装移行しやすい。
- `ANS` コード化と `PATTERN_RULES` 単一ソース化により、誤判定と保守コストを抑える設計になっている。
- テスト表が「判定」「UI」「単一HTML制約」に分かれており、デモ品質に必要な観点を押さえている。
- PII 最小化の基本方針（保存除外・匿名化デフォルト ON）は方向性として正しい。

### このラウンドでの対応
- **CS-R1-1（復元導線修正）** → §7.1 `btn-resume` の出現条件コメントを明記。§8.6 `init` を「`persist=local` ラジオの選択時にのみ `btn-resume` を表示・活性化」に改修し、`onResume` 冒頭に `persistMode==='local'` ガードを追加。§11.1.1 に 2 アクション強制条件を明文化。
- **CS-R1-2（再開時 persistMode 整合）** → §8.2 `Persist.save()` のペイロードに `persistMode` を含め、§8.6 `onResume` で `State.get().persistMode='local'` を明示セット。§11.1 に「復元後は persistMode=local を保証」を追記。
- **CS-R1-3（validateConfig 致命停止）** → §6.4 を改修し、`return warns.length===0` を継続しつつ、§8.6 `init` 冒頭で `if (!validateConfig()) { Render.disableStartButtons(); return; }` を必須化。§9.1 エラー分類表の挙動欄に `init 中断` を追記。§8.5 Render 公開関数に `disableStartButtons()` を追加。
- **CS-R1-4（営業メモ印字真理値表固定）** → §10.3 の条件を「`printSalesMemo===true` のときのみ印字（匿名化トグルはマスキング可否のみ担当）」に書き換え。§11.3 の `salesMemo` 印刷条件も同様に修正し、匿名化 OFF 単独では印字しないことを明記。
- **CS-R1-5（PII スキーマ統一）** → §4.3 の `pii` を `{ companyName:'', contactName:'', date:'' }` に拡張。§11.3 / §12 / §4.5 / §10.2 の匿名化・除外対象を `companyName` / `contactName` / `salesMemo` で統一。
- **MS-R1-1（PATTERN_RULES 優先順記録）** → 仕様書（実装直前フェーズ）側の §6.2 を正とする。根拠を付録B「決定記録」に追記（法対応 E を最優先、次いで拡張計画 C、次いで多事業所 D、複数拠点 B、基本 A の順。設計書の例示と差分がある点を明記）。
- **MS-R1-2（ruleLabel と calcCFull の整合）** → §6.2 の E ルールの `ruleLabel` を `'C=3（法対応要整備：Q16 未整備/わからない OR Q17 未整備/わからない OR Q6=NO）'` に修正し、`Q17=PART` は C=2（Eには昇格しない）であることを明示。§8.4 `calcCFull` のコメントを揃えて説明と実装の齟齬を排除。
- **MS-R1-3（printDetailModel typedef 追加）** → §10.3 に `@typedef PrintDetailModel` を追加（header/answers/matchedRule/checkList/hearingTags/salesMemo の 6 列必須）。§8.5 Render 公開関数の `Render.toPrint(mode)` 入出力契約コメントを追記。
- **MS-R1-4（終了コード N/A）** → §9 冒頭に「本プロジェクトはブラウザ実行のため終了コード定義なし（N/A）」を明記。
- **MS-R1-5（UIテスト4本追加）** → §13.2 に T-UI-11〜T-UI-14 を追加（resume表示条件、resume時 persistMode=local、validateConfig 失敗時 start 不可、salesMemo 印字真理値表）。
- **MS-R1-6（型契約追加）** → §4.4 / §8.2 / §8.3 に `@typedef JudgeResult` / `@typedef FlowProgress` / `@typedef PersistPayload` を追加。`State.applySnapshot()` で上書きされ得るキーの最小必須集合を §8.1 に明記。
- **mS-R1-1** → §5 見出しを「QUESTIONS 辞書（ID キー）」に修正し、§5.1 本文内の「配列」を「辞書」に統一。
- **mS-R1-2** → §7.1 progressbar の `aria-valuemax` 初期値はダミーであり Render が即時更新する旨のコメントを追記。§7.3 ARIA 方針にも「Flow.progress() に連動して都度更新」を明記。
- **mS-R1-3** → §4.5 および §8.2 に「`appVersion` は `v1` 固定。将来 v2 以降を導入する場合は非互換キーとして旧データを破棄する（移行処理なし）」を明記。
- **mS-R1-4** → §4.4 / §8.4 の `reasonHighlights.axis` 列挙値に `'EXT'` を正式追加し、scores には含めないことを注記。
- **mS-R1-5** → §8.1 `State.applySnapshot()` のコメントに「`ui` / `pii` / `salesMemo` は復元対象外（浅いマージで破損しないよう保存ペイロード側から除外）」を明記。

### 見送り
- なし（Critical 5件／Major 6件／Minor 5件すべて反映）。いずれも単一HTML／外部依存ゼロ／オフライン動作の絶対条件、および要件・設計書の本質仕様（決定表、ショート版7問、派遣法免責）の整合を維持したまま処理。

## ラウンド2 (2026-04-23)

### 総合評価

**C**
実装粒度は高い一方、**保存再開フローと詳細版データ定義に実害級の穴**が残っていた。Critical 3件（空セッション保存、PATTERNS.detail 未定義、PII UI の DOM 未落とし込み）と Major 5件を処理すれば Phase5 着手可能な水準に戻せる内容。

### Critical 指摘

- **CS-R2-1. 保存モード切替で「空セッション」を保存でき、再開が壊れる**
  - `none→local` で即 `Persist.save()` すると `mode='splash' / currentQid=null` が保存される。`PersistPayload.mode` が `'full'|'short'` と矛盾。
  - 修正方針: `save()` 前に `mode in {full,short} && currentQid` を必須化、`load()` でスキーマ検証失敗時は `clear()+false`。
- **CS-R2-2. `PATTERNS.detail` が実質未定義で、M-06/M-07 詳細版のチェックリストが作れない**
  - 修正方針: A〜E の `detail` を最低 `category/label/status` まで完全定義。
- **CS-R2-3. PII 入力トグル/入力欄の UI 仕様が DOM 骨格に落ちていない**
  - 「企業名等を入力する」トグル（§11.3）が `result`/`print` の骨格サンプルに無い。
  - 修正方針: `result`/`print` それぞれの DOM id・イベント・マスキング動作を明示追加。

### Major 指摘

- **MS-R2-1. Q17=PART の扱いが要件決定表と不一致**
  - 要件§10.3.2 は E 条件に「一部のみ」を含むが、仕様書（R1で反転）は除外。
  - 修正方針: 要件書を正として仕様書を戻す（`Q17=PART` も E に昇格する）。設計書のトレーサビリティもあわせて明記。
- **MS-R2-2. 設計書とのトレーサビリティ差分が残存**
  - `PATTERN_RULES` 優先順、`printDetailModel` 列（`answerCode/status` 欠落）などが設計本文と不一致。
  - 修正方針: 設計書を仕様に追随（優先順は仕様§6.2 を正、`answerCode/status` は仕様側に列を追加）。
- **MS-R2-3. 営業メモの UI 文言が真理値表と矛盾**
  - `textarea` placeholder が「匿名化OFFまたはサブトグルONで印字」となっているが真理値表はサブトグル ON のみ。
  - 修正方針: 文言を真理値表（§11.3.1）に揃える。
- **MS-R2-4. `load()` のペイロード妥当性検証が弱く、破損 JSON で画面遷移が壊れうる**
  - 修正方針: 必須キー/型チェックを追加し、失敗時は `clear()+false`。
- **MS-R2-5. テスト不足**
  - 「空セッション再開」「破損ペイロード」「PIIトグル DOM 存在確認」が 13 章に無い。
  - 修正方針: UI/異常系テストを3本追加。

### Minor 指摘

- **mS-R2-1** 見出しが「`QUESTIONS` 配列スキーマ」のまま。用語統一。
- **mS-R2-2** 「本番 `console.*` なし」と `validateConfig` の `console.warn` の文言整合。
- **mS-R2-3** 依存バージョン節に「Python/ライブラリ固定は N/A」を1行。

### このラウンドでの対応

- **CS-R2-1（空セッション保存の防止）** → §8.2 `Persist.save()` 冒頭に `mode in {full,short} && currentQid` ガードを追加。`load()` に必須キー／型検証を追加し、失敗時は `clear()+false`。§11.1 の即時保存規約を「`none→local` 切替時は `mode==='splash'` の間は save しない（質問開始時の Persist.save が最初の保存タイミング）」に書き換え。§8.6 `onPersistChange` の `none→local` 即時 save を「保存可能な状態のときのみ save」へ改修。
- **CS-R2-2（PATTERNS.detail 完全定義）** → §6.1 の A〜E 各 `detail` を `{ category, label, status }` 配列として完全定義し、M-06/M-07 詳細版チェックリストの生成元として確定。
- **CS-R2-3（PII トグル／入力欄 DOM 明示）** → §7.1 の `screen-result` に「企業名等を入力する」トグル（`btn-toggle-pii`）と `pii-fields`（`inp-company-name` / `inp-contact-name` / `inp-date`）を追加。§7.1 の `screen-print` にも印刷プレビュー時のマスキング動作仕様を明示。§8.5 Render に `togglePiiFields()` / `maskPiiField(el)` を追加し、§11.3 にイベントと ID 対応表を追記。
- **MS-R2-1（Q17=PART の一本化）** → 要件§10.3.2（E 条件に「一部のみ」を含む）を正とし、§6.2 の E `ruleLabel` と §8.4 `calcCFull` のコメントを「`Q17=PART` は C=3（E に昇格）」に書き戻す。付録B 決定記録に「R1 の暫定反転を R2 で要件書に揃えて再反転」と記録。
- **MS-R2-2（設計書とのトレーサビリティ）** → 仕様書§6.2 の優先順（1:E→2:C→3:D→4:B→5:A）を正とし、設計書§5.2.2 の列記は初期ドラフトである旨を付録B に追記。`PrintAnswer` に `answerCode`、`PrintChecklistItem` に `status`（'推奨'|'要確認'|'要ヒアリング'）列を追加して設計書§5.2 の列を完全反映。
- **MS-R2-3（営業メモ UI 文言統一）** → §7.1 `textarea#sales-memo` の placeholder を「（詳細版印刷時のみ・『営業メモを印字する』トグル ON のときだけ印字）」に修正（§11.3.1 真理値表に一致）。
- **MS-R2-4（`load()` 妥当性検証強化）** → §8.2 `Persist.load()` に必須キー（`appVersion`/`mode`/`persistMode`/`answers`/`history`）と型（`mode` ∈ {full,short}、`currentQid` が string）のチェックを追加。失敗時は `clear()+false`。
- **MS-R2-5（追加テスト 3 本）** → §13.2 に T-UI-15（空セッション再開が発生しないこと）、T-UI-16（破損ペイロードで復元が走らず splash に戻る）、T-UI-17（`screen-result` に `btn-toggle-pii` / `pii-fields` が存在し、トグルで表示状態が切替わる）を追加。
- **mS-R2-1** → §5.1 / §4.2 見出しの「配列スキーマ」表記を「辞書スキーマ」に統一。
- **mS-R2-2** → §9.3 に「ただし `validateConfig` が構成不整合を検出した場合のみ `console.warn` を出力する」ことを追記し、§6.4 コメントも文言を揃える。
- **mS-R2-3** → §2.3 に「Python／npm 等のライブラリバージョン固定は N/A（Vanilla JS・外部依存ゼロのため）」を 1 行追記。

### 見送り

- なし（Critical 3件／Major 5件／Minor 3件すべて反映）。単一 HTML／外部依存ゼロ／オフライン動作、および要件書の本質仕様（決定表、ショート版7問、派遣法免責）は維持。

## ラウンド3 (2026-04-23) ※最終

### 総合評価

**B（条件付きGo）** （推移: R1 C → R2 C → R3 B）
仕様の完成度は高く、単一HTML・オフライン前提も維持されている。実装直前として「印刷免責の実現方法」と「復元データ検証」を潰すことで Phase5 に進める水準。Critical 1件／Major 3件／Minor 3件を処理して "十分実用的" として切り上げる。

### Critical 指摘

- **CS-R3-1. 印刷免責の要件と実装契約が不整合（§7.1, §10.3, §10.5）**
  - 「各ページへ複製」と書いている一方、提示 CSS/DOM では先頭 1 回表示しか担保できない。
  - 修正方針: `position: fixed` で全ページ反復表示する方式に固定。要件側は「全ページ表示」のまま、実装契約（CSS）を合わせる。テストに「2 ページ以上で全ページ表示」を追加。

### Major 指摘

- **MS-R3-1. `Persist.load()` の妥当性検証が型チェック止まり（§8.2）**
  - `currentQid` が `QUESTIONS` に存在するか、`shortIndex` と `SHORT_ROUTE` の整合などが未検証。
  - 修正方針: `currentQid in QUESTIONS`、`history` 要素検証（string かつ `QUESTIONS` に存在）、`shortIndex` 範囲、`mode='short'` 時の `currentQid===SHORT_ROUTE[shortIndex]` を必須化。
- **MS-R3-2. Render 責務定義の自己矛盾（§8.5）**
  - 「Render は State を読むのみ」としつつ `updateResumeButton()` は実質 `Persist.hasSavedSession()` 依存。
  - 修正方針: 判定は AppCore 側で行い、Render には boolean 引数（`show: boolean`）を渡す形に寄せる。
- **MS-R3-3. テスト期待値が曖昧（§13.1 T9/T10）**
  - 「A/B 近傍」「-」は回帰判定不能。
  - 修正方針: pattern/priority/tags を単一の期待値に固定（T9/T10 は fallback=6 など明示）。

### Minor 指摘

- **mS-R3-1.** ショート版の P 軸扱いが暗黙（§8.4 `calcP`）。Q1 未回答時に実質 `COARSE` になる仕様を明文化する。
- **mS-R3-2.** `validateConfig()` の検査範囲が狭い（§6.4）。priority 重複・欠番・`QUESTIONS` 参照整合まで見る。
- **mS-R3-3.** レビュー観点 E の汎用エッジケースの N/A 整理不足（24:00/CP932 混在など本案件非該当項目）。N/A 理由を明記して論点を閉じる。

### 良かった点（R3 レビュアー指摘）

- トレーサビリティ表と `PATTERN_RULES` 単一ソース化が明確で、実装者の迷いが少ない。
- PII 除外・匿名化トグル・営業メモ印字真理値表まで落とし込めており、デモ用途として実用的。
- 単一 HTML 完結・外部依存禁止・`file://` 前提・検証項目（T-FILE 系）が一貫している。

### このラウンドでの対応

- **CS-R3-1（印刷免責の全ページ反復を実装契約として固定）** → §10.4 の印刷用 CSS を `.disclaimer-print { position: fixed; top: 0; left: 0; right: 0; }` ＋ `body { margin-top: 14mm; }` に変更し、全ページで物理的に反復表示されることを保証。§10.5 の文言を「`position: sticky` は印刷で初頁しか出ないため不採用。`position: fixed` に `@page` 余白確保を組み合わせて全ページ反復表示する」に更新。§7.1 のコメントも「CSS `@media print` で `position: fixed` により全ページ反復」に書き換え。§13.2 に T-UI-18（詳細版印刷で 2 ページ以上になった場合、2 ページ目以降にも `.disclaimer-print` が表示される）を追加。
- **MS-R3-1（`Persist.load()` 整合チェック強化）** → §8.2 `isValidPayload()` に以下を追加。①`snap.currentQid in QUESTIONS` を必須化、②`history` 配列の各要素が string かつ `QUESTIONS` に存在すること、③`shortIndex` が 0 以上かつ `SHORT_ROUTE.length` 未満（short 時）または 0（full 時）、④`mode==='short'` のときは `currentQid === SHORT_ROUTE[shortIndex]` を必須化。失敗時は `clear()+false`。§11.1 の `Persist.load()` 説明にもこの整合条件を追記。
- **MS-R3-2（Render/AppCore 責務境界の整理）** → §8.5 `Render.updateResumeButton(show: boolean)` に改め、boolean 引数で表示/非表示・活性/非活性を更新するのみに限定（Persist/Flow/Judge を直接呼ばない設計§3.2 を厳守）。§8.6 `AppCore.init()` / `onPersistChange()` の側で `const show = Persist.isAvailable() && Persist.hasSavedSession() && persistRadio==='local'` を計算し `Render.updateResumeButton(show)` を呼ぶ形に変更。§11.1.1 の記述も「AppCore 側で 3 条件を論理積、Render は boolean を受けて DOM を更新するのみ」に揃える。
- **MS-R3-3（曖昧テスト期待値の確定）** → §13.1 T9 を `pattern=A / priority=6 / fallback=true / tags=[Q12 わからない, 省略項目あり, 要ヒアリング（確定度: 中）]` に固定（Q2 も Q3 も未回答で scores={L:1,A:1,C:2} のため `nearestPattern` は A）。T10 は `pattern=A / priority=5 / tags=[Q13 未確定（C 不変を確認）]` に固定（他 NO で A 発火）。fallback 発火ケースは T8 と T9 のみ、priority=6 固定。
- **mS-R3-1（ショート版 P 軸扱い明文化）** → §8.4 `calcP` に「ショート版は Q1 が `SHORT_ROUTE` に含まれるため通常回答される。仮に Q1 が未回答（`a.Q1 === undefined`）の場合は `COARSE` 扱いとし、P 軸を未評価扱いにはしない」コメントを追記。§5.2 ショート版ルート説明にも「Q1 で P 軸を評価する」旨を 1 行追記。
- **mS-R3-2（validateConfig 検査範囲拡張）** → §6.4 に以下を追加。①`priority` 値の重複／欠番検出（1..N の連番必須）、②`PATTERN_RULES` 各ルールの `predicate` が関数であること、③`PATTERNS[pid].detail` が配列で最低 1 要素以上持つこと、④`buildReasonHighlights` の `qids` が `QUESTIONS` に存在すること（参照整合）。失敗メッセージは `warns[]` に push し、§9.3 方針どおり `console.warn` として出力。
- **mS-R3-3（N/A 観点整理）** → §9 冒頭の MS-R1-4 注記に続けて「N/A 観点一覧」として「①日時: 24:00 等の境界値 → 入力は `<input type=date>` のみのため N/A、②文字コード: CP932/UTF-8 混在 → 単一 HTML（UTF-8 固定）のため N/A、③プロセス終了コード（MS-R1-4 既出） → ブラウザ実行のため N/A、④i18n: 日本語単一のため N/A」を明記して論点を閉じる。

### 見送り

- なし（Critical 1件／Major 3件／Minor 3件すべて反映）。単一 HTML／外部依存ゼロ／オフライン動作、要件書の本質仕様（決定表、ショート版 7 問、派遣法免責）はすべて維持。

## 最終残論点

- **実装直前の残論点はなし**。R3 Critical/Major/Minor はすべて反映済み。Phase5（単一 HTML 実装）着手可能。
- **Phase5 初動で確定する項目**（仕様書に既定で盛り込み済みだが実装で最終値化するもの）:
  1. 付録 A の配色（パターン A〜E の CSS 変数最終値、印刷モノクロ識別可能性の実機確認）。
  2. `#app-header` の sticky 時高さと `.disclaimer-print` の `position: fixed` 余白（14mm 目安）の実機調整。印刷実機で 2 ページ以上レイアウトが崩れないこと（T-UI-18）。
  3. ショート版 4 分以内（T-UI-1）の実測。QA 通過後に要件書 M-01 の数値をコミット値として確定。
- **将来拡張（Phase5 スコープ外・メモ）**: 複数名の担当者入力、多言語化、PDF 直書き出しは現行仕様のスコープ外。仕様書の拡張フィールド（`reasonHighlights.axis='EXT'`）は今後 Q15=YES 以外の拡張計画フラグを受け入れる余地として維持。
