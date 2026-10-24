import { useId } from 'react';

import './rubric-editor.css';

type JsonObject = Record<string, unknown>;

export type RubricVisualEditorProps = {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  readOnly: boolean;
};

const SCORING_MODE = 'PROPORTIONAL_CHECKLIST_V0';
const isObject = (value: unknown): value is JsonObject =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): string => typeof value === 'string' ? value : '';
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const display = (value: unknown): string =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : 'Chưa có';

function nextKey(prefix: string, values: unknown[], field: string): string {
  const existing = new Set(values.filter(isObject).map((value) => value[field]));
  let number = 1;
  while (existing.has(`${prefix}${number}`)) number += 1;
  return `${prefix}${number}`;
}

function PlusIcon() {
  return <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
    <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
  </svg>;
}

function RemoveButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return <button type="button" className="rubric-remove" aria-label={label} title={label} disabled={disabled} onClick={onClick}>
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M4 6h12M8 3h4l1 3H7l1-3ZM6 6l1 11h6l1-11M9 9v5M11 9v5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </button>;
}

export function RubricVisualEditor({ value, onChange, disabled, readOnly }: RubricVisualEditorProps) {
  const editorId = useId();
  let definition: JsonObject | null = null;
  let parseError = '';
  try {
    const parsed: unknown = JSON.parse(value);
    if (!isObject(parsed) || !Array.isArray(parsed.criteria) || typeof parsed.max_score !== 'number') {
      parseError = 'Nội dung cần có điểm tối đa (max_score) và danh sách tiêu chí (criteria).';
    } else definition = parsed;
  } catch {
    parseError = 'Nội dung rubric chưa đọc được. Mở phần JSON nâng cao bên dưới để sửa hoặc nhập lại file rubric.';
  }

  const criteria = list(definition?.criteria);
  const allChecklists = criteria.filter(isObject).flatMap((criterion) => list(criterion.checklists));
  const allRequirements = allChecklists.filter(isObject).flatMap((checklist) => list(checklist.requirements));
  const totalWeight = criteria.reduce<number>((sum, criterion) =>
    sum + (isObject(criterion) && typeof criterion.weight === 'number' ? criterion.weight : 0), 0);
  const maxScore = typeof definition?.max_score === 'number' ? definition.max_score : 0;
  const weightsMatch = Math.abs(totalWeight - maxScore) < 0.000001;
  const locked = disabled || readOnly;

  function updateDefinition(patch: JsonObject) {
    if (definition === null || locked) return;
    onChange(JSON.stringify({ ...definition, ...patch }, null, 2));
  }

  function updateCriterion(criterionIndex: number, patch: JsonObject) {
    const criterion = criteria[criterionIndex];
    if (!isObject(criterion)) return;
    updateDefinition({ criteria: criteria.map((item, index) => index === criterionIndex ? { ...criterion, ...patch } : item) });
  }

  function updateChecklist(criterionIndex: number, checklistIndex: number, patch: JsonObject) {
    const criterion = criteria[criterionIndex];
    if (!isObject(criterion)) return;
    const checklists = list(criterion.checklists);
    const checklist = checklists[checklistIndex];
    if (!isObject(checklist)) return;
    updateCriterion(criterionIndex, {
      checklists: checklists.map((item, index) => index === checklistIndex ? { ...checklist, ...patch } : item),
    });
  }

  function updateRequirement(criterionIndex: number, checklistIndex: number, requirementIndex: number, patch: JsonObject) {
    const criterion = criteria[criterionIndex];
    if (!isObject(criterion)) return;
    const checklist = list(criterion.checklists)[checklistIndex];
    if (!isObject(checklist)) return;
    const requirements = list(checklist.requirements);
    const requirement = requirements[requirementIndex];
    if (!isObject(requirement)) return;
    const updated = { ...requirement, ...patch };
    if (updated.description === '') delete updated.description;
    updateChecklist(criterionIndex, checklistIndex, {
      requirements: requirements.map((item, index) => index === requirementIndex ? updated : item),
    });
  }

  function duplicateKey(items: unknown[], field: string, key: unknown): boolean {
    return items.filter((item) => isObject(item) && item[field] === key).length > 1;
  }

  const advancedJson = <details className="rubric-advanced" open={parseError ? true : undefined}>
    <summary><span>JSON nâng cao</span><small>Dành cho cấu hình chi tiết và kiểm tra dữ liệu</small></summary>
    <div className="rubric-advanced-body">
      <p className="rubric-help">Các trường cấu hình bổ sung được giữ nguyên khi sửa bằng biểu mẫu.</p>
      <label className="rubric-field">
        <span>Rubric definition JSON</span>
        <textarea aria-label="Rubric definition JSON" className="rubric-json" value={value} onChange={(event) => onChange(event.target.value)}
          disabled={disabled} readOnly={readOnly} spellCheck={false} rows={16} />
      </label>
    </div>
  </details>;

  if (definition === null) return <div className="rubric-visual-editor">
    <div className="rubric-warning" role="alert"><strong>Chưa thể hiển thị tiêu chí</strong><p>{parseError}</p></div>
    {advancedJson}
  </div>;

  return <section className="rubric-visual-editor" aria-labelledby={`${editorId}-heading`}>
    <div className="rubric-section-heading">
      <div><span className="rubric-eyebrow">Cấu trúc rubric</span><h3 id={`${editorId}-heading`}>Tiêu chí & bằng chứng</h3></div>
      <span className="rubric-scoring-pill">Tỷ lệ checklist · v0</span>
    </div>
    <p className="rubric-intro">Mỗi tiêu chí gồm các phát biểu cần kiểm chứng và yêu cầu bằng chứng cụ thể.</p>

    <div className="rubric-score-overview">
      {readOnly ? <div className="rubric-score-readonly"><span>Điểm tối đa</span><strong>{maxScore}<small>điểm</small></strong></div>
        : <label className="rubric-field rubric-max-score"><span>Điểm tối đa</span><div className="rubric-score-input">
          <input type="number" min="0.01" step="any" value={maxScore} disabled={disabled}
            onChange={(event) => { if (Number.isFinite(event.target.valueAsNumber)) updateDefinition({ max_score: event.target.valueAsNumber }); }} />
          <span aria-hidden="true">điểm</span>
        </div></label>}
      <div className="rubric-allocation"><span>Tổng trọng số tiêu chí</span><strong>{Number(totalWeight.toFixed(6))} <small>/ {maxScore} điểm</small></strong>
        <span className={`rubric-allocation-state ${weightsMatch && maxScore > 0 ? 'is-valid' : 'is-invalid'}`}>
          {maxScore <= 0 ? 'Điểm tối đa phải lớn hơn 0' : weightsMatch ? 'Đã phân bổ đủ điểm' : 'Cần khớp với điểm tối đa'}
        </span>
      </div>
      <div className="rubric-structure-count"><strong>{String(criteria.length).padStart(2, '0')}</strong><span>tiêu chí</span><small>{allChecklists.length} checklist</small></div>
    </div>

    <div className="rubric-criteria-stack">
      {criteria.map((criterion, criterionIndex) => {
        if (!isObject(criterion)) return <div className="rubric-warning" key={criterionIndex}>
          Tiêu chí {criterionIndex + 1} có cấu trúc chưa được hỗ trợ. Dữ liệu được giữ nguyên trong JSON nâng cao.
          {!readOnly && <button type="button" className="rubric-text-button" disabled={disabled}
            onClick={() => updateDefinition({ criteria: criteria.filter((_, index) => index !== criterionIndex) })}>Xóa tiêu chí {criterionIndex + 1}</button>}
        </div>;
        const checklists = list(criterion.checklists);
        const hasLevels = criterion.levels !== undefined && (!Array.isArray(criterion.levels) || criterion.levels.length > 0);
        const unsupportedCriterion = hasLevels || criterion.scoring_mode !== SCORING_MODE
          || !Array.isArray(criterion.checklists)
          || (criterion.title !== undefined && typeof criterion.title !== 'string')
          || (criterion.criterion_key !== undefined && typeof criterion.criterion_key !== 'string')
          || (criterion.weight !== undefined && typeof criterion.weight !== 'number');
        const criterionReadOnly = readOnly || unsupportedCriterion;
        const criterionName = text(criterion.title) || `Tiêu chí ${criterionIndex + 1}`;
        return <article className="rubric-criterion-card" key={criterionIndex} aria-labelledby={`${editorId}-criterion-${criterionIndex}`}>
          <header className="rubric-criterion-header">
            <span className="rubric-criterion-number">{String(criterionIndex + 1).padStart(2, '0')}</span>
            <div><span className="rubric-eyebrow">Tiêu chí {criterionIndex + 1}</span><h4 id={`${editorId}-criterion-${criterionIndex}`}>{criterionName}</h4></div>
            <span className="rubric-points-pill">{display(criterion.weight)} điểm</span>
            {!criterionReadOnly && <RemoveButton label={`Xóa tiêu chí ${criterionIndex + 1}`} disabled={disabled}
              onClick={() => updateDefinition({ criteria: criteria.filter((_, index) => index !== criterionIndex) })} />}
          </header>
          <div className="rubric-criterion-body">
            {unsupportedCriterion && <div className="rubric-warning" role="note"><strong>{hasLevels ? 'Thang mức tùy chỉnh chưa được hỗ trợ' : 'Tiêu chí có cấu hình chưa được hỗ trợ'}</strong>
              <p>Tiêu chí này chỉ hiển thị để bảo toàn cấu hình gốc. Phiên bản hiện tại chỉ chấm điểm theo tỷ lệ checklist; cấu hình tùy chỉnh cần được kiểm tra trong JSON nâng cao trước khi publish.</p></div>}
            {criterionReadOnly ? <div className="rubric-readonly-meta"><span>Mã tiêu chí <code>{display(criterion.criterion_key)}</code></span><span>Trọng số <strong>{display(criterion.weight)} điểm</strong></span></div>
              : <div className="rubric-criterion-fields">
                <label className="rubric-field rubric-title-field"><span>Tên tiêu chí</span><input type="text" value={text(criterion.title)}
                  placeholder="Nhập tên tiêu chí" disabled={disabled} maxLength={10000} onChange={(event) => updateCriterion(criterionIndex, { title: event.target.value })} /></label>
                <label className="rubric-field"><span>Mã tiêu chí</span><input type="text" value={text(criterion.criterion_key)} disabled={disabled} maxLength={128}
                  onChange={(event) => updateCriterion(criterionIndex, { criterion_key: event.target.value })} /></label>
                <label className="rubric-field"><span>Trọng số (điểm)</span><input type="number" min="0.01" step="any" value={typeof criterion.weight === 'number' ? criterion.weight : ''} disabled={disabled}
                  onChange={(event) => { if (Number.isFinite(event.target.valueAsNumber)) updateCriterion(criterionIndex, { weight: event.target.valueAsNumber }); }} /></label>
              </div>}
            {duplicateKey(criteria, 'criterion_key', criterion.criterion_key) && <p className="rubric-inline-warning">Mã tiêu chí đang trùng. Mỗi tiêu chí cần một mã riêng.</p>}
            {!criterionReadOnly && !text(criterion.title).trim() && <p className="rubric-inline-warning">Điền tên tiêu chí trước khi lưu.</p>}
            {!criterionReadOnly && !text(criterion.criterion_key).trim() && <p className="rubric-inline-warning">Mã tiêu chí không được để trống.</p>}
            {typeof criterion.weight === 'number' && criterion.weight <= 0 && <p className="rubric-inline-warning">Trọng số phải lớn hơn 0.</p>}

            <div className="rubric-subsection-heading"><h5>Checklist kiểm chứng <span>{checklists.length}</span></h5><span>Phát biểu có thể đối chiếu với bằng chứng</span></div>
            {checklists.length === 0 && <p className="rubric-empty-copy">Thêm checklist và tự mô tả điều cần kiểm chứng cho tiêu chí này.</p>}
            <div className="rubric-checklist-stack">
              {checklists.map((checklist, checklistIndex) => {
                if (!isObject(checklist)) return <p className="rubric-warning" key={checklistIndex}>Checklist {checklistIndex + 1} có cấu trúc chưa được hỗ trợ. Xem JSON nâng cao để kiểm tra.</p>;
                const requirements = list(checklist.requirements);
                const unsupportedChecklist = !Array.isArray(checklist.requirements)
                  || typeof checklist.statement !== 'string' || typeof checklist.checklist_key !== 'string'
                  || !['LOCAL', 'GRAPH'].includes(text(checklist.evidence_mode))
                  || (checklist.importance !== undefined && !['CORE', 'REQUIRED', 'OPTIONAL'].includes(text(checklist.importance)));
                const checklistReadOnly = criterionReadOnly || unsupportedChecklist;
                const checklistLabel = `${criterionIndex + 1}.${checklistIndex + 1}`;
                return <section className="rubric-atomic-card" key={checklistIndex} aria-label={`Checklist ${checklistLabel}`}>
                  <div className="rubric-atomic-heading"><span className="rubric-check-icon" aria-hidden="true">✓</span><strong>Checklist {checklistLabel}</strong>
                    {checklistReadOnly ? <span className="rubric-mode-badge">{display(checklist.evidence_mode)}</span>
                      : <RemoveButton label={`Xóa checklist ${checklistLabel}`} disabled={disabled}
                        onClick={() => updateCriterion(criterionIndex, { checklists: checklists.filter((_, index) => index !== checklistIndex) })} />}
                  </div>
                  {unsupportedChecklist && <p className="rubric-inline-warning">Cấu hình checklist chưa được hỗ trợ. Các trường gốc được giữ trong JSON nâng cao.</p>}
                  {checklistReadOnly ? <><p className="rubric-readonly-statement">{display(checklist.statement)}</p><div className="rubric-readonly-meta"><span>Mã <code>{display(checklist.checklist_key)}</code></span><span>Mức quan trọng <strong>{display(checklist.importance ?? 'REQUIRED')}</strong></span></div></>
                    : <>
                      <label className="rubric-field"><span>Phát biểu cần kiểm chứng</span><textarea aria-label="Phát biểu cần kiểm chứng" rows={2} value={text(checklist.statement)} disabled={disabled}
                        placeholder="Mô tả một điều cụ thể cần kiểm chứng trong báo cáo" maxLength={10000}
                        onChange={(event) => updateChecklist(criterionIndex, checklistIndex, { statement: event.target.value })} /></label>
                      <div className="rubric-checklist-fields">
                        <label className="rubric-field"><span>Mã checklist</span><input type="text" value={text(checklist.checklist_key)} disabled={disabled} maxLength={128}
                          onChange={(event) => updateChecklist(criterionIndex, checklistIndex, { checklist_key: event.target.value })} /></label>
                        <label className="rubric-field"><span>Phạm vi bằng chứng</span><select value={text(checklist.evidence_mode)} disabled={disabled}
                          onChange={(event) => updateChecklist(criterionIndex, checklistIndex, { evidence_mode: event.target.value })}>
                          <option value="LOCAL">LOCAL · Một vùng nội dung</option><option value="GRAPH">GRAPH · Liên kết nhiều vùng</option>
                        </select></label>
                        <label className="rubric-field"><span>Mức quan trọng</span><select value={text(checklist.importance) || 'REQUIRED'} disabled={disabled}
                          onChange={(event) => updateChecklist(criterionIndex, checklistIndex, { importance: event.target.value })}>
                          <option value="CORE">CORE · Cốt lõi</option><option value="REQUIRED">REQUIRED · Bắt buộc</option><option value="OPTIONAL">OPTIONAL · Tùy chọn</option>
                        </select></label>
                      </div>
                    </>}
                  {duplicateKey(allChecklists, 'checklist_key', checklist.checklist_key) && <p className="rubric-inline-warning">Mã checklist đang trùng trong rubric.</p>}
                  {!checklistReadOnly && !text(checklist.statement).trim() && <p className="rubric-inline-warning">Điền phát biểu cần kiểm chứng trước khi lưu.</p>}
                  {!checklistReadOnly && !text(checklist.checklist_key).trim() && <p className="rubric-inline-warning">Mã checklist không được để trống.</p>}
                  <div className="rubric-requirements">
                    <div className="rubric-requirements-heading"><h6>Yêu cầu bằng chứng</h6><span>{requirements.length} yêu cầu</span></div>
                    <p className="rubric-help">Mỗi yêu cầu là một phần bằng chứng cần tìm. Các cách diễn đạt thay thế trong cùng yêu cầu được nối bằng “hoặc”.</p>
                    {requirements.length === 0 && <p className="rubric-inline-warning">Cần ít nhất {checklist.evidence_mode === 'GRAPH' ? 'hai yêu cầu cho GRAPH' : 'một yêu cầu bằng chứng'}. Bạn cần tự nhập nội dung và cách diễn đạt cần tìm.</p>}
                    {checklist.evidence_mode === 'GRAPH' && requirements.length === 1 && <p className="rubric-inline-warning">GRAPH cần ít nhất hai yêu cầu bằng chứng được soạn rõ ràng.</p>}
                    {requirements.map((requirement, requirementIndex) => {
                      if (!isObject(requirement)) return <p className="rubric-warning" key={requirementIndex}>Yêu cầu {requirementIndex + 1} có cấu trúc chưa được hỗ trợ. Dữ liệu được giữ trong JSON nâng cao.</p>;
                      const alternatives = list(requirement.any_of);
                      const unsupportedRequirement = typeof requirement.requirement_id !== 'string'
                        || !Array.isArray(requirement.any_of) || !alternatives.every((item) => typeof item === 'string')
                        || (requirement.description !== undefined && typeof requirement.description !== 'string');
                      const requirementReadOnly = checklistReadOnly || unsupportedRequirement;
                      const requirementLabel = `${checklistLabel}.${requirementIndex + 1}`;
                      return <div className="rubric-requirement" key={requirementIndex}>
                        <div className="rubric-requirement-top"><strong>Yêu cầu {requirementIndex + 1}</strong>
                          {requirementReadOnly ? <code>{display(requirement.requirement_id)}</code>
                            : <RemoveButton label={`Xóa yêu cầu ${requirementLabel}`} disabled={disabled}
                              onClick={() => updateChecklist(criterionIndex, checklistIndex, { requirements: requirements.filter((_, index) => index !== requirementIndex) })} />}
                        </div>
                        {unsupportedRequirement && <p className="rubric-inline-warning">Yêu cầu có cấu trúc chưa được hỗ trợ. Kiểm tra dữ liệu gốc trong JSON nâng cao.</p>}
                        {requirementReadOnly ? <>{typeof requirement.description === 'string' && <p className="rubric-readonly-description">{requirement.description}</p>}
                          <ul className="rubric-alternative-list">{alternatives.map((alternative, index) => <li key={index}>{display(alternative)}</li>)}</ul></>
                          : <>
                            <div className="rubric-requirement-fields">
                              <label className="rubric-field"><span>Mô tả <small>(không bắt buộc)</small></span><input type="text" value={text(requirement.description)} disabled={disabled} maxLength={10000}
                                placeholder="Nội dung bằng chứng cần có" onChange={(event) => updateRequirement(criterionIndex, checklistIndex, requirementIndex, { description: event.target.value })} /></label>
                              <label className="rubric-field"><span>Mã yêu cầu</span><input type="text" value={text(requirement.requirement_id)} disabled={disabled} maxLength={128}
                                onChange={(event) => updateRequirement(criterionIndex, checklistIndex, requirementIndex, { requirement_id: event.target.value })} /></label>
                            </div>
                            <span className="rubric-alternatives-label">Cách diễn đạt cần tìm <small>Khớp ít nhất một cách diễn đạt</small></span>
                            {alternatives.map((alternative, alternativeIndex) => <div className="rubric-alternative-row" key={alternativeIndex}>
                              <span aria-hidden="true">{alternativeIndex === 0 ? 'Tìm' : 'hoặc'}</span>
                              <input type="text" aria-label={`Cách diễn đạt ${alternativeIndex + 1} của yêu cầu ${requirementLabel}`} value={text(alternative)} disabled={disabled} maxLength={10000}
                                placeholder="Nhập cụm từ hoặc cách diễn đạt được chấp nhận"
                                onChange={(event) => updateRequirement(criterionIndex, checklistIndex, requirementIndex, {
                                  any_of: alternatives.map((item, index) => index === alternativeIndex ? event.target.value : item),
                                })} />
                              <RemoveButton label={`Xóa cách diễn đạt ${alternativeIndex + 1} của yêu cầu ${requirementLabel}`} disabled={disabled}
                                onClick={() => updateRequirement(criterionIndex, checklistIndex, requirementIndex, { any_of: alternatives.filter((_, index) => index !== alternativeIndex) })} />
                            </div>)}
                            <button type="button" className="rubric-text-button" disabled={disabled} onClick={() => updateRequirement(criterionIndex, checklistIndex, requirementIndex, { any_of: [...alternatives, ''] })}>
                              <PlusIcon /> Thêm cách diễn đạt</button>
                          </>}
                        {alternatives.length === 0 && <p className="rubric-inline-warning">Thêm ít nhất một cách diễn đạt để xác định bằng chứng cần tìm.</p>}
                        {alternatives.some((item) => typeof item === 'string' && !item.trim()) && <p className="rubric-inline-warning">Điền các cách diễn đạt còn trống trước khi lưu.</p>}
                        {duplicateKey(allRequirements, 'requirement_id', requirement.requirement_id) && <p className="rubric-inline-warning">Mã yêu cầu đang trùng trong rubric.</p>}
                        {!requirementReadOnly && !text(requirement.requirement_id).trim() && <p className="rubric-inline-warning">Mã yêu cầu không được để trống.</p>}
                      </div>;
                    })}
                    {!checklistReadOnly && <button type="button" className="rubric-text-button rubric-add-requirement" disabled={disabled}
                      onClick={() => updateChecklist(criterionIndex, checklistIndex, { requirements: [...requirements, {
                        requirement_id: nextKey('R', allRequirements, 'requirement_id'), any_of: [''],
                      }] })}><PlusIcon /> Thêm yêu cầu bằng chứng</button>}
                  </div>
                </section>;
              })}
            </div>
            {!criterionReadOnly && <button type="button" className="rubric-add-checklist" disabled={disabled} onClick={() => updateCriterion(criterionIndex, {
              checklists: [...checklists, { checklist_key: nextKey(`${text(criterion.criterion_key) || 'C'}.`, allChecklists, 'checklist_key'),
                statement: '', evidence_mode: 'LOCAL', importance: 'REQUIRED', requirements: [] }],
            })}><PlusIcon /> Thêm checklist kiểm chứng</button>}
          </div>
        </article>;
      })}
    </div>
    {criteria.length === 0 && <div className="rubric-empty-state"><strong>Rubric chưa có tiêu chí</strong><p>Thêm tiêu chí đầu tiên, phân bổ điểm và mô tả bằng chứng cần kiểm chứng.</p></div>}
    {!readOnly && <button type="button" className="rubric-add-criterion" disabled={disabled} onClick={() => updateDefinition({ criteria: [...criteria, {
      criterion_key: nextKey('C', criteria, 'criterion_key'), title: '', weight: 1, scoring_mode: SCORING_MODE, checklists: [],
    }] })}><PlusIcon /> Thêm tiêu chí đánh giá</button>}
    <p className="rubric-scoring-note">Điểm tiêu chí được tính theo tỷ lệ checklist đáp ứng, trong giới hạn trọng số đã phân bổ. Hệ thống không suy diễn yêu cầu bằng chứng từ tên tiêu chí.</p>
    {advancedJson}
  </section>;
}
