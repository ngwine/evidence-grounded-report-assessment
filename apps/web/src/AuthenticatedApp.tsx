import { useEffect, useRef, useState, type FormEvent } from 'react';

import {
  AuthenticatedApiError, bootstrapSession, cloneRubricVersion, createRubric,
  getRubric, getRubricVersion, listRubrics, listRubricVersions, listWorkspaces, login, logout,
  operationKey, publishRubricVersion, updateRubricDraft,
} from './authenticatedApi';
import type { Actor, Page, Rubric, RubricDefinition, RubricVersion, Workspace } from './authenticatedApi';
import './authenticated.css';
import AuthenticatedReports from './AuthenticatedReports';
import { RubricVisualEditor } from './RubricVisualEditor';

const TEMPLATE: RubricDefinition = {
  max_score: 10,
  criteria: [{
    criterion_key: 'C1', title: 'Phương pháp và kết quả', weight: 10,
    scoring_mode: 'PROPORTIONAL_CHECKLIST_V0',
    checklists: [{
      checklist_key: 'C1.1', statement: 'Báo cáo nêu phương pháp đánh giá kết quả.',
      evidence_mode: 'LOCAL', importance: 'REQUIRED',
      requirements: [{ requirement_id: 'method', any_of: ['phương pháp đánh giá'] }],
    }],
  }],
};

function describeError(error: unknown): string {
  if (!(error instanceof AuthenticatedApiError)) return 'Không kết nối được API. Kiểm tra backend rồi thử lại.';
  if (error.code === 'INVALID_CREDENTIALS') return 'Email hoặc mật khẩu chưa đúng, hoặc tài khoản không còn hoạt động.';
  if (error.status === 401) return 'Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục.';
  if (error.status === 429) return 'Đã có nhiều lần đăng nhập. Chờ một lúc rồi thử lại.';
  if (error.status === 403) return error.code === 'CSRF_INVALID'
    ? 'Phiên bảo vệ đã thay đổi. Tải lại trang trước khi tiếp tục.' : 'Tài khoản không có quyền thực hiện thao tác này.';
  if (error.status === 404) return 'Không tìm thấy nội dung trong workspace này, hoặc quyền truy cập đã thay đổi.';
  if (error.code === 'REVISION_CONFLICT') return 'Nội dung đã được cập nhật ở nơi khác. Tải lại bản mới trước khi sửa tiếp.';
  if (error.code === 'SESSION_CHANGED') return 'Phiên đăng nhập đã thay đổi trong lúc tải trang. Tải lại trang để đồng bộ phiên.';
  if (error.code === 'RUBRIC_IMMUTABLE') return 'Version này đã được publish. Tạo một draft mới để chỉnh sửa.';
  if (error.code === 'RUBRIC_CONFLICT') return 'Mã rubric này đã tồn tại trong workspace.';
  if (error.code === 'RUBRIC_COMPILATION_FAILED') return `Rubric chưa thể publish. Kiểm tra atomic requirements, trọng số và scoring mode. ${error.message}`;
  if (error.status === 422) return `Nội dung chưa đúng cấu trúc. ${error.message}`;
  if (error.status === 503) return 'Dịch vụ dữ liệu đang không sẵn sàng. Chưa có xác nhận lưu thành công; có thể thử lại.';
  return 'Chưa thực hiện được yêu cầu. Thử tải lại dữ liệu rồi thao tác lại.';
}

function parseDefinition(text: string): RubricDefinition {
  const parsed: unknown = JSON.parse(text);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('definition');
  const value = parsed as Record<string, unknown>;
  if (typeof value.max_score !== 'number' || !Array.isArray(value.criteria)) throw new Error('definition');
  return value as RubricDefinition;
}

export default function AuthenticatedApp() {
  const [actor, setActor] = useState<Actor | null>(null);
  const [starting, setStarting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [workspaces, setWorkspaces] = useState<Page<Workspace> | null>(null);
  const [workspaceId, setWorkspaceId] = useState('');
  const [rubrics, setRubrics] = useState<Page<Rubric> | null>(null);
  const [selected, setSelected] = useState<Rubric | null>(null);
  const [version, setVersion] = useState<RubricVersion | null>(null);
  const [versions, setVersions] = useState<Page<RubricVersion> | null>(null);
  const [rubricKey, setRubricKey] = useState('');
  const [title, setTitle] = useState('');
  const [editor, setEditor] = useState('');
  const [creating, setCreating] = useState(false);
  const [section, setSection] = useState<'analysis' | 'documents' | 'rubrics'>('analysis');
  const [loadingRubrics, setLoadingRubrics] = useState(false);
  const selectedWorkspace = useRef('');
  const requestSequence = useRef(0);
  const createKey = useRef<{ body: string; key: string } | null>(null);
  const cloneKey = useRef<{ body: string; key: string } | null>(null);
  const canManage = actor?.memberships.some((membership) =>
    membership.workspace_id === workspaceId && membership.capabilities.includes('rubric.manage')) ?? false;
  const unsaved = version !== null && editor !== JSON.stringify(version.definition, null, 2);
  const dirty = creating ? Boolean(editor.trim() || rubricKey.trim() || title.trim()) : unsaved;

  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', guard);
    return () => { window.removeEventListener('beforeunload', guard); };
  }, [dirty]);

  function clearAcademicState() {
    requestSequence.current += 1;
    selectedWorkspace.current = '';
    setWorkspaces(null); setWorkspaceId(''); setRubrics(null);
    setSelected(null); setVersion(null); setVersions(null); setCreating(false); setEditor('');
    setRubricKey(''); setTitle('');
    createKey.current = null; cloneKey.current = null;
  }

  function fail(cause: unknown) {
    setError(describeError(cause));
    setRequestId(cause instanceof AuthenticatedApiError ? cause.requestId : null);
    if (cause instanceof AuthenticatedApiError && cause.status === 401) {
      setActor(null); clearAcademicState();
    }
  }

  useEffect(() => {
    let active = true;
    bootstrapSession().then((value) => { if (active) setActor(value); }).catch((cause: unknown) => {
      if (active && (!(cause instanceof AuthenticatedApiError) || cause.status !== 401)) fail(cause);
    }).finally(() => { if (active) setStarting(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (actor === null) return;
    let active = true;
    listWorkspaces().then((page) => { if (active) setWorkspaces(page); }).catch((cause) => { if (active) fail(cause); });
    return () => { active = false; };
  }, [actor]);

  useEffect(() => {
    if (!workspaceId && workspaces?.items.length === 1) setWorkspaceId(workspaces.items[0].id);
  }, [workspaceId, workspaces]);

  useEffect(() => {
    selectedWorkspace.current = workspaceId;
    requestSequence.current += 1;
    setSelected(null); setVersion(null); setVersions(null); setEditor(''); setCreating(false); setRubrics(null);
    setError(null); setNotice(null); setRequestId(null);
    if (!workspaceId || !canManage) { setLoadingRubrics(false); return; }
    let active = true;
    setLoadingRubrics(true);
    listRubrics(workspaceId).then((page) => { if (active) setRubrics(page); })
      .catch((cause) => { if (active) fail(cause); })
      .finally(() => { if (active) setLoadingRubrics(false); });
    return () => { active = false; };
  }, [workspaceId, canManage]);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null); setRequestId(null);
    try { setActor(await login(email.trim(), password)); setPassword(''); }
    catch (cause) { setPassword(''); fail(cause); }
    finally { setBusy(false); }
  }

  async function signOut() {
    if (dirty && !window.confirm('Bỏ thay đổi chưa lưu và đăng xuất?')) return;
    setBusy(true); setError(null);
    try { await logout(); setActor(null); clearAcademicState(); setNotice(null); }
    catch (cause) { fail(cause); }
    finally { setBusy(false); }
  }

  async function openRubric(rubric: Rubric) {
    if (dirty && !window.confirm('Bỏ các thay đổi chưa lưu để mở rubric khác?')) return;
    const scope = workspaceId;
    const sequence = ++requestSequence.current;
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      const parent = await getRubric(scope, rubric.id);
      const current = await getRubricVersion(scope, parent.current_version_id);
      const allVersions = await listRubricVersions(scope, parent.id);
      if (selectedWorkspace.current !== scope || sequence !== requestSequence.current) return;
      setSelected(parent); setVersion(current); setCreating(false);
      setVersions(allVersions);
      setRubricKey(parent.rubric_key); setTitle(parent.title);
      setEditor(JSON.stringify(current.definition, null, 2));
    } catch (cause) { if (selectedWorkspace.current === scope) fail(cause); }
    finally { setBusy(false); }
  }

  async function saveDraft() {
    let definition: RubricDefinition;
    try { definition = parseDefinition(editor); }
    catch { setError('JSON chưa hợp lệ. Definition cần có max_score và criteria.'); return; }
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      if (creating) {
        const body = { rubric_key: rubricKey, title, definition };
        const serialized = JSON.stringify(body);
        if (createKey.current?.body !== serialized) createKey.current = { body: serialized, key: operationKey() };
        const created = await createRubric(workspaceId, body, createKey.current.key);
        const draft = await getRubricVersion(workspaceId, created.current_version_id);
        setSelected(created); setVersion(draft); setCreating(false);
        setVersions(await listRubricVersions(workspaceId, created.id));
        setEditor(JSON.stringify(draft.definition, null, 2));
        createKey.current = null;
        setRubrics(await listRubrics(workspaceId));
      } else if (version !== null) {
        const updated = await updateRubricDraft(workspaceId, version, definition);
        setVersion(updated); setEditor(JSON.stringify(updated.definition, null, 2));
        if (selected) setVersions(await listRubricVersions(workspaceId, selected.id));
      }
      setNotice('Đã lưu draft. Chỉ version publish thành công mới được dùng để phân tích.');
    } catch (cause) { fail(cause); }
    finally { setBusy(false); }
  }

  async function publish() {
    if (version === null || selected === null || unsaved) return;
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      const published = await publishRubricVersion(workspaceId, version);
      setVersion(published); setSelected(await getRubric(workspaceId, selected.id));
      setVersions(await listRubricVersions(workspaceId, selected.id));
      setNotice('Đã publish version bất biến. Muốn thay đổi nội dung, tạo draft mới.');
    } catch (cause) { fail(cause); }
    finally { setBusy(false); }
  }

  async function clone() {
    if (selected === null || version === null) return;
    if (unsaved && !window.confirm('Clone nội dung đã lưu, không bao gồm thay đổi chưa lưu. Tiếp tục?')) return;
    setBusy(true); setError(null); setNotice(null); setRequestId(null);
    try {
      const serialized = `${selected.id}:${selected.revision}:${version.id}`;
      if (cloneKey.current?.body !== serialized) cloneKey.current = { body: serialized, key: operationKey() };
      const draft = await cloneRubricVersion(workspaceId, selected, version, cloneKey.current.key);
      setVersion(draft); setEditor(JSON.stringify(draft.definition, null, 2));
      setSelected(await getRubric(workspaceId, selected.id));
      setVersions(await listRubricVersions(workspaceId, selected.id));
      cloneKey.current = null;
      setNotice(`Đã tạo draft version ${draft.version_no}. Version được publish trước đó vẫn giữ nguyên.`);
    } catch (cause) { fail(cause); }
    finally { setBusy(false); }
  }

  async function importDefinition(file?: File) {
    if (file === undefined) return;
    if (file.size > 1_000_000) { setError('File rubric cần nhỏ hơn 1 MB.'); return; }
    setBusy(true);
    try {
      const text = await file.text();
      const parsed: unknown = JSON.parse(text);
      const authored = parsed as Record<string, unknown>;
      const isCreate = parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) && 'definition' in authored;
      const definition = parseDefinition(isCreate ? JSON.stringify(authored.definition) : text);
      if (isCreate && creating) {
        if (typeof authored.rubric_key === 'string') setRubricKey(authored.rubric_key);
        if (typeof authored.title === 'string') setTitle(authored.title);
      }
      setEditor(JSON.stringify(definition, null, 2)); setError(null); setNotice('Đã đọc file vào editor; nội dung chưa được lưu.');
    } catch { setError('File chưa phải RubricDefinition hoặc CreateRubricRequest JSON hợp lệ.'); }
    finally { setBusy(false); }
  }

  const feedback = <div aria-live="polite">
    {error && <div className="notice notice-error" role="alert">{error}{requestId && <small>Mã yêu cầu: {requestId}</small>}</div>}
    {notice && <div className="notice">{notice}</div>}
  </div>;

  return <div className={`app-shell authenticated-shell ${actor ? 'workspace-shell' : 'login-shell'}`}>
    <a className="skip-link" href="#main">Đến nội dung chính</a>
    {actor && <aside className="workspace-sidebar" aria-label="Điều hướng chính">
      <a href="#main" className="workspace-brand" onClick={() => setSection('analysis')}><span className="workspace-brand-mark" aria-hidden="true">e<span>.</span></span><div><strong>evidence</strong><small>REPORT INTELLIGENCE</small></div></a>
      <p className="sidebar-caption">KHÔNG GIAN GIẢNG VIÊN</p>
      <nav>{([
        ['analysis', 'Phân tích báo cáo', '◫'],
        ['documents', 'Kho tài liệu', '▤'],
        ['rubrics', 'Rubric đánh giá', '☷'],
      ] as const).map(([id, name, icon]) => <button key={id} className={`workspace-nav ${section === id ? 'is-active' : ''}`} aria-current={section === id ? 'page' : undefined} onClick={() => {
        if (!dirty || section === id || window.confirm('Giữ nguyên bản nháp rubric và chuyển màn hình?')) setSection(id);
      }}><span aria-hidden="true">{icon}</span>{name}{section === id && <span className="nav-active-dot" aria-hidden="true" />}</button>)}</nav>
      <div className="sidebar-principle"><span className="sidebar-principle-mark" aria-hidden="true">↗</span><strong>Bằng chứng trước.<br />Kết luận sau.</strong><p>Mỗi nhận xét gắn với đoạn văn, nguồn và phiên bản tài liệu.</p></div>
      <div className="sidebar-footer"><span className="live-dot" /> Local workspace <small>Hỗ trợ giảng viên · không tự chấm điểm chính thức</small></div>
    </aside>}
    <div className="workspace-body">
    <header className="site-header workspace-topbar">
      {actor ? <div className="workspace-breadcrumb"><span>Không gian làm việc</span><span aria-hidden="true">/</span><strong>{section === 'analysis' ? 'Phân tích báo cáo' : section === 'documents' ? 'Kho tài liệu' : 'Rubric đánh giá'}</strong></div> : <div className="brand"><span className="brand-mark" aria-hidden="true">e.</span><strong>evidence</strong></div>}
      {actor && <div className="header-right"><span className="local-runtime-badge"><span />Chạy trên máy của bạn</span><div className="workspace-user"><span className="user-avatar" aria-hidden="true">{actor.display_name.trim().charAt(0).toUpperCase()}</span><span>{actor.display_name}<small>Giảng viên</small></span></div><button className="subtle-button" disabled={busy} onClick={signOut}>Đăng xuất</button></div>}
    </header>
    <main id="main">
      {starting ? <p role="status">Đang kiểm tra phiên đăng nhập…</p> : actor === null ? <div className="login-layout"><section className="login-story"><span className="eyebrow">EVIDENCE-GROUNDED ASSESSMENT</span><h1>Đọc sâu hơn.<br />Đánh giá có<br /><em>cơ sở hơn.</em></h1><p>Một không gian để đối chiếu nội dung, đánh giá theo rubric và xem lại bằng chứng trong báo cáo sinh viên.</p><div className="login-feature"><span>01</span><div><strong>Đối chiếu nội dung</strong><p>Tìm đoạn liên quan và truy về tài liệu nguồn.</p></div></div><div className="login-feature"><span>02</span><div><strong>Đánh giá theo rubric</strong><p>Mỗi checklist đi kèm evidence và lý do đánh giá.</p></div></div><small>Phân tích hỗ trợ quyết định. Giảng viên luôn là người review.</small></section><section className="panel auth-login">
        <span className="eyebrow">CHÀO MỪNG TRỞ LẠI</span><h2>Đăng nhập</h2>
        <p className="section-intro">Tiếp tục vào không gian đánh giá của bạn.</p>
        {feedback}
        <form onSubmit={signIn}>
          <label className="field-label" htmlFor="auth-email">Email</label>
          <input id="auth-email" type="email" autoComplete="username" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} />
          <label className="field-label" htmlFor="auth-password">Mật khẩu</label>
          <input id="auth-password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} />
          <button className="primary-button submit-button" disabled={busy}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
        </form>
        <p className="login-private-note"><span aria-hidden="true">◇</span> Tài liệu và model được xử lý tại máy local.</p>
      </section></div> : <>
        <div className="workspace-page-heading"><div><span className="eyebrow">{section === 'analysis' ? 'TỪ BÁO CÁO ĐẾN BẰNG CHỨNG' : section === 'documents' ? 'QUẢN LÝ ĐẦU VÀO' : 'TIÊU CHÍ RÕ RÀNG, NHẤT QUÁN'}</span><h1>{section === 'analysis' ? 'Phân tích báo cáo' : section === 'documents' ? 'Kho tài liệu' : 'Rubric đánh giá'}</h1><p>{section === 'analysis' ? 'Đối chiếu nguồn và đánh giá theo rubric trong cùng một lượt phân tích.' : section === 'documents' ? 'Báo cáo, nguồn đối chứng và các phiên bản được lưu trong một nơi.' : 'Soạn tiêu chí, yêu cầu evidence và khóa phiên bản trước khi sử dụng.'}</p></div><span className="workspace-version">BẢN THỬ NGHIỆM <span>·</span> LOCAL</span></div>
        {feedback}
        <section className="panel auth-workspace-select">
          <label className="field-label" htmlFor="auth-workspace">Workspace</label>
          <select id="auth-workspace" value={workspaceId} disabled={busy || workspaces === null} onChange={(event) => {
            if (!dirty || window.confirm('Bỏ thay đổi chưa lưu để chuyển workspace?')) setWorkspaceId(event.target.value);
          }}><option value="">{workspaces === null ? 'Đang tải workspace…' : 'Chọn workspace'}</option>
            {workspaces?.items.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name} · {workspace.key}</option>)}
          </select>
          {workspaces?.items.length === 0 && <p className="field-help">Tài khoản chưa có workspace hoạt động. Liên hệ người quản lý để được cấp quyền.</p>}
          {workspaces?.page.has_more && <button className="subtle-button" disabled={busy} onClick={async () => {
            setBusy(true);
            try { const page = await listWorkspaces(workspaces.page.next_cursor); setWorkspaces({ ...page, items: [...workspaces.items, ...page.items] }); }
            catch (cause) { fail(cause); } finally { setBusy(false); }
          }}>Tải thêm workspace</button>}
        </section>
        {workspaces?.items.find((item) => item.id === workspaceId)?.key === 'demo-midterm-20261024' && <div className="demo-data-banner"><strong>DỮ LIỆU MINH HỌA</strong><span>Report và nguồn được tự viết để trình diễn luồng. Các số hiển thị không phải kết quả thực nghiệm trên dữ liệu nghiên cứu.</span></div>}
        {workspaceId && !canManage && <div className="notice notice-muted">Bạn có quyền vào workspace này nhưng không có quyền quản lý rubric. Nội dung học thuật không được mở rộng theo quyền quản trị hệ thống.</div>}
        {workspaceId && canManage && <div className="auth-rubric-grid" hidden={section !== 'rubrics'}>
          <aside className="panel">
            <div className="panel-title"><h2>Rubric</h2><button className="subtle-button" disabled={busy} onClick={() => {
              if (dirty && !window.confirm('Bỏ thay đổi chưa lưu để tạo rubric?')) return;
              setCreating(true); setSelected(null); setVersion(null); setVersions(null); setEditor(JSON.stringify(TEMPLATE, null, 2)); setRubricKey(''); setTitle(''); setNotice(null); setError(null);
            }}>Tạo rubric</button></div>
            {loadingRubrics && <p role="status">Đang tải rubric…</p>}
            {rubrics?.items.length === 0 && <p className="section-intro">Workspace chưa có rubric. Tạo draft đầu tiên hoặc nhập definition JSON.</p>}
            <ul className="auth-rubric-list">{rubrics?.items.map((rubric) => <li key={rubric.id}><button disabled={busy} aria-current={selected?.id === rubric.id ? 'true' : undefined} onClick={() => openRubric(rubric)}><strong>{rubric.title}</strong><small>{rubric.rubric_key}</small></button></li>)}</ul>
            {rubrics?.page.has_more && <button className="subtle-button" disabled={busy} onClick={async () => {
              setBusy(true);
              try { const page = await listRubrics(workspaceId, rubrics.page.next_cursor); setRubrics({ ...page, items: [...rubrics.items, ...page.items] }); }
              catch (cause) { fail(cause); } finally { setBusy(false); }
            }}>Tải thêm rubric</button>}
          </aside>
          <section className="panel">
            {!creating && version === null ? <><h2>Chọn một rubric</h2><p className="section-intro">Mở rubric để xem version hiện tại, hoặc tạo draft mới.</p></> : <>
              <div className="panel-title"><h2>{creating ? 'Rubric mới' : `Version ${version?.version_no}`}</h2>{version && <span className="panel-chip">{version.status === 'DRAFT' ? 'Draft' : version.status === 'PUBLISHED' ? 'Published · bất biến' : 'Retired'}</span>}</div>
              {version && versions && <>
                <label className="field-label" htmlFor="rubric-version">Các version đã lưu</label>
                <select id="rubric-version" value={version.id} disabled={busy} onChange={async (event) => {
                  if (dirty && !window.confirm('Bỏ thay đổi chưa lưu để mở version khác?')) return;
                  const id = event.target.value;
                  setBusy(true); setError(null); setNotice(null);
                  try { const chosen = await getRubricVersion(workspaceId, id); setVersion(chosen); setEditor(JSON.stringify(chosen.definition, null, 2)); }
                  catch (cause) { fail(cause); } finally { setBusy(false); }
                }}>
                  {!versions.items.some((item) => item.id === version.id) && <option value={version.id}>Version {version.version_no} · {version.status}</option>}
                  {versions.items.map((item) => <option key={item.id} value={item.id}>Version {item.version_no} · {item.status}{item.id === selected?.current_version_id ? ' · hiện tại' : ''}</option>)}
                </select>
                {versions.page.has_more && selected && <button className="subtle-button" disabled={busy} onClick={async () => {
                  setBusy(true);
                  try { const page = await listRubricVersions(workspaceId, selected.id, versions.page.next_cursor); setVersions({ ...page, items: [...versions.items, ...page.items] }); }
                  catch (cause) { fail(cause); } finally { setBusy(false); }
                }}>Tải thêm version</button>}
              </>}
              <label className="field-label" htmlFor="rubric-key">Mã rubric</label>
              <input id="rubric-key" value={rubricKey} disabled={busy || !creating} maxLength={128} onChange={(event) => setRubricKey(event.target.value)} />
              <label className="field-label" htmlFor="rubric-title">Tên rubric</label>
              <input id="rubric-title" value={title} disabled={busy || !creating} maxLength={500} onChange={(event) => setTitle(event.target.value)} />
              {(creating || version?.status === 'DRAFT') && <details className="auth-editor-tools"><summary>Nhập file và công cụ nâng cao</summary><div className="auth-actions">
                <label>Nhập JSON<input type="file" accept=".json,application/json" disabled={busy} onChange={(event) => { void importDefinition(event.target.files?.[0]); event.target.value = ''; }} /></label>
                <button className="subtle-button" disabled={busy} onClick={() => { if (!editor || window.confirm('Thay nội dung editor bằng cấu trúc mẫu?')) { setEditor(JSON.stringify(TEMPLATE, null, 2)); setNotice('Đây là cấu trúc minh họa. Cần thay yêu cầu và alternatives theo rubric thực tế trước khi dùng.'); } }}>Cấu trúc mẫu</button>
              </div></details>}
              <RubricVisualEditor value={editor} onChange={setEditor} disabled={busy} readOnly={!creating && version?.status !== 'DRAFT'} />
              {version && <details className="technical-details"><summary>Thông tin phiên bản</summary><p className="field-help">Revision {version.revision} · SHA-256 <code>{version.rubric_sha256}</code></p></details>}
              {unsaved && <p className="field-help">Có thay đổi chưa lưu. Lưu draft trước khi publish.</p>}
              <div className="auth-actions">
                {(creating || version?.status === 'DRAFT') && <button className="primary-button" disabled={busy || !editor.trim() || !rubricKey.trim() || !title.trim()} onClick={saveDraft}>{busy ? 'Đang thực hiện…' : 'Lưu draft'}</button>}
                {version?.status === 'DRAFT' && <button className="secondary-button" disabled={busy || unsaved} onClick={publish}>Kiểm tra & publish</button>}
                {version && <button className="subtle-button" disabled={busy} onClick={clone}>Clone thành draft mới</button>}
                {selected && <button className="subtle-button" disabled={busy} onClick={() => openRubric(selected)}>Tải lại bản hiện tại</button>}
              </div>
            </>}
          </section>
        </div>}
        {workspaceId && <div hidden={section === 'rubrics'}><AuthenticatedReports key={workspaceId} actor={actor} workspaceId={workspaceId}
          view={section === 'documents' ? 'documents' : 'analysis'} onViewChange={setSection}
          rubricRefreshKey={`${version?.id ?? ''}:${version?.revision ?? ''}`} onAuthenticationError={fail} /></div>}
        <p className="safe-note">Phân tích tạo proposal có version và evidence để review; không tự công bố điểm chính thức hoặc kết luận đạo văn.</p>
      </>}
    </main>
    </div>
  </div>;
}
