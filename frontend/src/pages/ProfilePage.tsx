import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  CalendarDays,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  Globe,
  Lock,
  Mail,
  Pencil,
  Send,
  ShieldCheck,
  Upload,
  Wallet,
  X,
} from 'lucide-react';
import { useAuth } from '@/shared/hooks/useAuth';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { rolesApi, type ActivateBusinessPayload } from '@/shared/api/roles';
import { BecomeBusinessForm } from '@/shared/onboarding/BecomeBusinessForm';
import { cn } from '@/shared/utils/cn';

interface ProfileData {
  id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  phone: string | null;
  timezone: string;
  language: string;
  email_verified_at: string | null;
  status: string;
  created_at: string | null;
  roles: Array<{ role: string; status: string }>;
  country: string | null;
  city: string | null;
  telegram: string | null;
  website: string | null;
  password_changed_at: string | null;
  partner_id: number | null;
  partner_since: string | null;
  business_since: string | null;
  payout_method: string | null;
  payout_currency: string | null;
  min_payout: number | null;
}

type ProfileForm = {
  first_name: string;
  last_name: string;
  phone: string;
  timezone: string;
  language: string;
  country: string;
  city: string;
  telegram: string;
  website: string;
};

type DataRow =
  | { label: string; key: keyof ProfileForm; kind: 'text' | 'country' | 'timezone' | 'language' }
  | { label: string; kind: 'readonly'; value: string };

const COUNTRIES = [
  { value: '', label: 'Не указана' },
  { value: 'RU', label: 'Россия' },
  { value: 'US', label: 'Соединённые Штаты' },
  { value: 'GB', label: 'Великобритания' },
  { value: 'DE', label: 'Германия' },
  { value: 'KZ', label: 'Казахстан' },
  { value: 'BY', label: 'Беларусь' },
  { value: 'UA', label: 'Украина' },
  { value: 'TR', label: 'Турция' },
];

const TIMEZONES = [
  'UTC',
  'Europe/Moscow',
  'Europe/Kaliningrad',
  'Europe/Samara',
  'Asia/Yekaterinburg',
  'Asia/Novosibirsk',
  'Asia/Vladivostok',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
];

const PAYOUT_LABELS: Record<string, string> = {
  bank_transfer: 'Банковский перевод',
  card: 'На карту',
  sbp: 'СБП',
};

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

function countryLabel(code?: string | null) {
  return COUNTRIES.find((item) => item.value === code)?.label || code || '—';
}

function languageLabel(code?: string | null) {
  return code === 'en' ? 'English' : 'Русский';
}

function initials(profile: ProfileData) {
  return (
    `${profile.first_name?.[0] || ''}${profile.last_name?.[0] || ''}`.toUpperCase() ||
    profile.email[0]?.toUpperCase() ||
    '?'
  );
}

function displayName(profile: ProfileData) {
  return [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.email;
}

function toForm(profile: ProfileData): ProfileForm {
  return {
    first_name: profile.first_name || '',
    last_name: profile.last_name || '',
    phone: profile.phone || '',
    timezone: profile.timezone || 'UTC',
    language: profile.language || 'ru',
    country: profile.country || '',
    city: profile.city || '',
    telegram: profile.telegram || '',
    website: profile.website || '',
  };
}

function resizeImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => {
      const canvas = document.createElement('canvas');
      const size = 160;
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        URL.revokeObjectURL(url);
        reject(new Error('canvas'));
        return;
      }
      const min = Math.min(image.width, image.height);
      const sx = (image.width - min) / 2;
      const sy = (image.height - min) / 2;
      ctx.drawImage(image, sx, sy, min, min, 0, 0, size, size);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.7));
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('image'));
    };
    image.src = url;
  });
}

export function ProfilePage() {
  const { session, logout } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const [businessOpen, setBusinessOpen] = useState(false);

  const { data: profile, isLoading } = useQuery<ProfileData>({
    queryKey: ['profile'],
    queryFn: () => api.get('/me'),
  });

  useEffect(() => {
    if (profile) setForm(toForm(profile));
  }, [profile]);

  const saveProfile = useMutation({
    mutationFn: (payload: ProfileForm) => api.patch<ProfileData>('/me', payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['profile'], data);
      queryClient.invalidateQueries({ queryKey: ['session'] });
      setEditing(false);
      addToast('Изменения сохранены', 'success');
    },
    onError: () => addToast('Не удалось сохранить профиль', 'error'),
  });

  const addBusinessRole = useMutation({
    mutationFn: (payload: ActivateBusinessPayload) => rolesApi.activateBusiness(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['session'], data);
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      setBusinessOpen(false);
      addToast('Роль Бизнеса подключена', 'success');
    },
    onError: () => addToast('Не удалось подключить роль. Попробуйте ещё раз.', 'error'),
  });

  const addPartnerRole = useMutation({
    mutationFn: () => rolesApi.activatePartner(profile ? displayName(profile) : undefined),
    onSuccess: (data) => {
      queryClient.setQueryData(['session'], data);
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      addToast('Роль Партнёра подключена', 'success');
    },
    onError: () => addToast('Не удалось подключить роль. Попробуйте ещё раз.', 'error'),
  });

  if (isLoading || !profile || !form) {
    return (
      <div className="h-full flex flex-col gap-3">
        <Skeleton className="h-8 w-64 rounded-lg" />
        <Skeleton className="h-20 rounded-xl" />
        <Skeleton className="flex-1 rounded-xl" />
      </div>
    );
  }

  const activeRoles = (profile.roles || []).filter((role) => role.status === 'active').map((role) => role.role);
  const hasBusiness = activeRoles.includes('business');
  const hasPartner = activeRoles.includes('partner');
  const activeRole = session?.active_role || (hasBusiness ? 'business' : 'partner');
  const dirty = JSON.stringify(form) !== JSON.stringify(toForm(profile));
  const since = activeRole === 'partner' ? profile.partner_since || profile.created_at : profile.business_since || profile.created_at;
  const roleNoun = activeRole === 'partner' ? 'Партнёр' : 'Бизнес';

  const dataRows: DataRow[] = [
    { label: 'Имя', key: 'first_name', kind: 'text' },
    { label: 'Фамилия', key: 'last_name', kind: 'text' },
    { label: 'Страна', key: 'country', kind: 'country' },
    { label: 'Город', key: 'city', kind: 'text' },
    { label: 'Email', value: profile.email, kind: 'readonly' },
    { label: 'Телефон', key: 'phone', kind: 'text' },
    { label: 'Telegram', key: 'telegram', kind: 'text' },
    { label: 'Часовой пояс', key: 'timezone', kind: 'timezone' },
    { label: 'Язык интерфейса', key: 'language', kind: 'language' },
  ];

  return (
    <div className="flex flex-col gap-3 h-full min-h-0 max-lg:overflow-auto lg:overflow-hidden">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between shrink-0">
        <div className="min-w-0">
          <h1 className="ui-page-title">Профиль пользователя</h1>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            Личные данные, безопасность и настройки аккаунта
            {editing && dirty ? ' · есть несохранённые изменения' : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          {editing ? (
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setForm(toForm(profile));
                  setEditing(false);
                }}
              >
                <X size={14} />
                Отмена
              </Button>
              <Button
                size="sm"
                onClick={() => saveProfile.mutate(form)}
                disabled={saveProfile.isPending || !dirty || !form.first_name.trim()}
              >
                <Check size={14} />
                {saveProfile.isPending ? 'Сохранение...' : 'Сохранить изменения'}
              </Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="secondary" onClick={() => setPasswordOpen(true)}>
                <Lock size={14} />
                Сменить пароль
              </Button>
              <Button size="sm" onClick={() => setEditing(true)}>
                <Pencil size={14} />
                Редактировать данные
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="ui-card px-4 py-3 shrink-0">
        <div className="flex items-center gap-4">
          <button type="button" onClick={() => setAvatarOpen(true)} className="relative shrink-0 group">
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-brand to-primary text-white flex items-center justify-center text-lg font-semibold overflow-hidden">
              {profile.avatar_url ? (
                <img src={profile.avatar_url} alt="" className="w-full h-full object-cover" />
              ) : (
                initials(profile)
              )}
            </div>
            <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-success border-2 border-card" />
            <span className="absolute inset-0 rounded-full bg-foreground/40 text-white opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
              <Upload size={14} />
            </span>
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight truncate">
                {[form.first_name, form.last_name].filter(Boolean).join(' ') || displayName(profile)}
              </h2>
              <span className="ui-badge bg-success/10 text-success">
                {profile.status === 'active' ? 'Активен' : profile.status}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {roleNoun} с {formatDate(since)}
              {profile.partner_id ? ` · ID партнёра: ${profile.partner_id}` : ''}
            </p>
            <div className="mt-1.5 hidden md:flex flex-nowrap gap-x-4 overflow-hidden text-xs text-muted-foreground">
              <MetaRow icon={Mail} value={profile.email} />
              <MetaRow icon={Globe} value={form.website || profile.website || '—'} />
              <MetaRow icon={Send} value={form.telegram || profile.telegram || '—'} />
              <MetaRow icon={Globe} value={form.timezone} />
              <MetaRow icon={CalendarDays} value={formatDate(profile.created_at)} />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 flex-1 min-h-0 overflow-hidden">
        <div className="ui-card p-4 flex flex-col min-h-0 overflow-hidden">
          <h2 className="ui-section-title shrink-0 mb-3">Пользовательские данные</h2>
          <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 min-h-0">
            {dataRows.map((row) => (
              <FieldControl
                key={row.label}
                row={row}
                form={form}
                editing={editing}
                onChange={(key, value) => setForm({ ...form, [key]: value })}
              />
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3 min-h-0 overflow-hidden">
          <div className="ui-card p-4 space-y-3 shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-md bg-accent text-primary flex items-center justify-center">
                <ShieldCheck size={16} />
              </div>
              <div className="min-w-0">
                <h2 className="ui-section-title">Безопасность</h2>
                <p className="text-xs text-muted-foreground">Надёжный пароль и контроль сессий</p>
              </div>
            </div>
            <Button size="sm" variant="secondary" className="w-full" onClick={() => setPasswordOpen(true)}>
              <Lock size={14} />
              Сменить пароль
            </Button>
            <p className="text-xs text-muted-foreground">
              Последнее изменение: {formatDate(profile.password_changed_at)}
            </p>
          </div>

          {hasPartner && (
            <div className="ui-card p-4 space-y-3 flex-1 min-h-0">
              <h2 className="ui-section-title">Платёжные реквизиты</h2>
              <dl className="space-y-1.5 text-sm">
                <InfoLine label="Метод" value={PAYOUT_LABELS[profile.payout_method || ''] || 'Не указан'} />
                <InfoLine label="Валюта" value={profile.payout_currency || 'RUB'} />
                <InfoLine
                  label="Минимум"
                  value={profile.min_payout != null ? `${profile.min_payout} ${profile.payout_currency || 'RUB'}` : '—'}
                />
              </dl>
              <Button
                size="sm"
                variant="secondary"
                className="w-full"
                onClick={() => {
                  if (activeRole !== 'partner') {
                    addToast('Переключитесь в пространство Партнёр, чтобы управлять реквизитами', 'info');
                    return;
                  }
                  navigate('/partner/settings');
                }}
              >
                <Wallet size={14} />
                Управление реквизитами
              </Button>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 min-h-0 overflow-hidden">
          <div className="ui-card p-4 space-y-3 flex-1 min-h-0">
            <h2 className="ui-section-title">Как вы используете RefIQ</h2>
            <RoleBlock
              title="Партнёр"
              active={hasPartner}
              description="Офферы, ссылки и вывод комиссий."
              items={['Ссылки', 'Офферы', 'Выплаты']}
              action={
                !hasPartner
                  ? {
                      label: addPartnerRole.isPending ? 'Подключение...' : 'Стать партнёром',
                      onClick: () => addPartnerRole.mutate(),
                      disabled: addPartnerRole.isPending,
                    }
                  : undefined
              }
            />
            <div className="border-t border-border/70" />
            <RoleBlock
              title="Бизнес"
              active={hasBusiness}
              description="Офферы, партнёры и выплаты комиссий."
              items={['Офферы', 'Партнёры', 'Выплаты']}
              action={!hasBusiness ? { label: 'Стать бизнесом', onClick: () => setBusinessOpen(true) } : undefined}
            />
          </div>

          <div className="ui-card p-4 space-y-2.5 shrink-0">
            <h2 className="ui-section-title">Аккаунт и верификация</h2>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Статус</span>
              <span className="ui-badge bg-success/10 text-success">
                {profile.status === 'active' ? 'Активен' : profile.status}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">Email</span>
              {profile.email_verified_at ? (
                <span className="inline-flex items-center gap-1 text-success truncate">
                  <CheckCircle2 size={14} />
                  <span className="truncate">{profile.email}</span>
                </span>
              ) : (
                <span className="text-muted-foreground truncate">{profile.email}</span>
              )}
            </div>
            <Button size="sm" variant="ghost" className="w-full text-muted-foreground" onClick={() => logout.mutate()}>
              Выйти
            </Button>
          </div>
        </div>
      </div>

      {passwordOpen && (
        <PasswordModal
          lastChanged={profile.password_changed_at}
          onClose={() => setPasswordOpen(false)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['profile'] });
            setPasswordOpen(false);
          }}
        />
      )}
      {avatarOpen && (
        <AvatarModal
          currentUrl={profile.avatar_url}
          initialsValue={initials(profile)}
          onClose={() => setAvatarOpen(false)}
          onSaved={(url) => {
            queryClient.setQueryData(['profile'], { ...profile, avatar_url: url });
            queryClient.invalidateQueries({ queryKey: ['session'] });
            setAvatarOpen(false);
          }}
        />
      )}
      {businessOpen && (
        <BecomeBusinessDrawer
          defaults={{
            website: form.website,
            country: form.country,
            work_email: profile.email,
            phone: form.phone,
          }}
          pending={addBusinessRole.isPending}
          onClose={() => setBusinessOpen(false)}
          onSubmit={(payload) => addBusinessRole.mutate(payload)}
        />
      )}
    </div>
  );
}

function FieldControl({
  row,
  form,
  editing,
  onChange,
}: {
  row: DataRow;
  form: ProfileForm;
  editing: boolean;
  onChange: (key: keyof ProfileForm, value: string) => void;
}) {
  const display =
    row.kind === 'readonly'
      ? row.value
      : row.kind === 'country'
        ? countryLabel(form.country)
        : row.kind === 'language'
          ? languageLabel(form.language)
          : form[row.key] || '—';

  return (
    <label className="min-w-0 block">
      <span className="text-[11px] leading-4 text-muted-foreground">{row.label}</span>
      {editing && row.kind !== 'readonly' ? (
        row.kind === 'country' ? (
          <select className="ui-input h-8 mt-0.5 px-2" value={form.country} onChange={(e) => onChange('country', e.target.value)}>
            {COUNTRIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        ) : row.kind === 'timezone' ? (
          <select className="ui-input h-8 mt-0.5 px-2" value={form.timezone} onChange={(e) => onChange('timezone', e.target.value)}>
            {TIMEZONES.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        ) : row.kind === 'language' ? (
          <select className="ui-input h-8 mt-0.5 px-2" value={form.language} onChange={(e) => onChange('language', e.target.value)}>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        ) : (
          <input
            className="ui-input h-8 mt-0.5 px-2"
            value={form[row.key]}
            onChange={(e) => onChange(row.key, e.target.value)}
          />
        )
      ) : (
        <span className="block text-sm font-medium truncate leading-5 mt-0.5">{display}</span>
      )}
    </label>
  );
}

function MetaRow({ icon: Icon, value }: { icon: typeof Mail; value: string }) {
  return (
    <div className="flex items-center gap-2 min-w-0 text-muted-foreground">
      <Icon size={14} className="shrink-0" />
      <span className="truncate text-foreground">{value}</span>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-right">{value}</dd>
    </div>
  );
}

function RoleBlock({
  title,
  active,
  description,
  items,
  action,
}: {
  title: string;
  active: boolean;
  description: string;
  items: string[];
  action?: { label: string; onClick: () => void; disabled?: boolean };
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">{title}</p>
        <span className={cn('ui-badge', active ? 'bg-success/10 text-success' : 'bg-muted text-muted-foreground')}>
          {active ? 'Активен' : 'Не подключён'}
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-snug">{description}</p>
      {active && <p className="text-xs text-muted-foreground">{items.join(' · ')}</p>}
      {action && (
        <Button size="sm" variant="secondary" className="w-full" onClick={action.onClick} disabled={action.disabled}>
          <Building2 size={14} />
          {action.label}
        </Button>
      )}
    </div>
  );
}

function PasswordModal({
  lastChanged,
  onClose,
  onSaved,
}: {
  lastChanged: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { addToast } = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [show, setShow] = useState(false);
  const [logoutOthers, setLogoutOthers] = useState(true);

  const checks = useMemo(
    () => [
      { label: 'Не менее 8 символов', ok: newPassword.length >= 8 },
      { label: 'Заглавная буква', ok: /[A-ZА-Я]/.test(newPassword) },
      { label: 'Строчная буква', ok: /[a-zа-я]/.test(newPassword) },
      { label: 'Цифра', ok: /\d/.test(newPassword) },
      { label: 'Спецсимвол', ok: /[^A-Za-zА-Яа-я0-9]/.test(newPassword) },
    ],
    [newPassword],
  );
  const score = checks.filter((item) => item.ok).length;
  const strength = score <= 2 ? 'Слабый' : score <= 4 ? 'Средний' : 'Надёжный';

  const changePassword = useMutation({
    mutationFn: () =>
      api.post('/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
        logout_other_sessions: logoutOthers,
      }),
    onSuccess: () => {
      addToast('Пароль обновлён', 'success');
      onSaved();
    },
    onError: () => addToast('Не удалось сменить пароль', 'error'),
  });

  const canSave = checks.every((item) => item.ok) && newPassword === confirmPassword && currentPassword.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="ui-section-title">Сменить пароль</h2>
            <p className="text-sm text-muted-foreground mt-1">Новый пароль будет использоваться при следующем входе.</p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <label className="block">
          <span className="ui-label">Текущий пароль</span>
          <input type="password" className="ui-input" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
        </label>
        <label className="block">
          <span className="ui-label">Новый пароль</span>
          <div className="relative">
            <input
              type={show ? 'text' : 'password'}
              className="ui-input pr-10"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              onClick={() => setShow((v) => !v)}
            >
              {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <div className="h-1.5 rounded-full bg-muted mt-2 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                score <= 2 ? 'bg-destructive w-1/3' : score <= 4 ? 'bg-warning w-2/3' : 'bg-success w-full',
              )}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-1">{strength}</p>
        </label>
        <label className="block">
          <span className="ui-label">Подтвердите новый пароль</span>
          <input type="password" className="ui-input" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
        </label>
        <ul className="space-y-1.5">
          {checks.map((item) => (
            <li key={item.label} className="flex items-center gap-2 text-sm">
              <span className={cn('w-4 h-4 rounded-full border flex items-center justify-center', item.ok && 'bg-success border-success text-white')}>
                {item.ok && <Check size={10} />}
              </span>
              <span className={item.ok ? 'text-foreground' : 'text-muted-foreground'}>{item.label}</span>
            </li>
          ))}
        </ul>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={logoutOthers} onChange={(e) => setLogoutOthers(e.target.checked)} />
          Выйти из всех других устройств
        </label>
        <div className="rounded-md bg-accent px-3 py-2 text-xs text-muted-foreground">
          Последнее изменение пароля: {formatDate(lastChanged)}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={!canSave || changePassword.isPending} onClick={() => changePassword.mutate()}>
            <Lock size={15} />
            Сохранить пароль
          </Button>
        </div>
      </div>
    </div>
  );
}

function AvatarModal({
  currentUrl,
  initialsValue,
  onClose,
  onSaved,
}: {
  currentUrl: string | null;
  initialsValue: string;
  onClose: () => void;
  onSaved: (url: string | null) => void;
}) {
  const { addToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(currentUrl);
  const saveAvatar = useMutation({
    mutationFn: (avatar_url: string | null) => api.patch('/me', { avatar_url }),
    onSuccess: (_data, avatar_url) => {
      addToast(avatar_url ? 'Аватар обновлён' : 'Аватар удалён', 'success');
      onSaved(avatar_url);
    },
    onError: () => addToast('Не удалось сохранить аватар', 'error'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between">
          <h2 className="ui-section-title">Изменить аватар</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="w-full rounded-lg border border-dashed border-border px-4 py-8 text-sm text-muted-foreground hover:bg-muted/40"
        >
          <Upload size={20} className="mx-auto mb-2" />
          Перетащите изображение сюда или выберите файл
          <span className="block text-xs mt-1">JPG, PNG, GIF до 2 МБ</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          className="hidden"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            if (file.size > 2 * 1024 * 1024) {
              addToast('Файл больше 2 МБ', 'error');
              return;
            }
            try {
              setPreview(await resizeImage(file));
            } catch {
              addToast('Не удалось прочитать изображение', 'error');
            }
          }}
        />
        <div className="flex items-center gap-4">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand to-primary text-white flex items-center justify-center text-2xl font-semibold overflow-hidden">
            {preview ? <img src={preview} alt="" className="w-full h-full object-cover" /> : initialsValue}
          </div>
          <div className="text-sm text-muted-foreground">Предпросмотр 128×128</div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <Button variant="ghost" className="text-destructive" onClick={() => saveAvatar.mutate(null)}>
            Удалить текущее фото
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              Отмена
            </Button>
            <Button disabled={!preview || saveAvatar.isPending} onClick={() => saveAvatar.mutate(preview)}>
              Сохранить аватар
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function BecomeBusinessDrawer({
  defaults,
  pending,
  onClose,
  onSubmit,
}: {
  defaults: {
    website?: string;
    country?: string;
    work_email?: string;
    phone?: string;
  };
  pending: boolean;
  onClose: () => void;
  onSubmit: (payload: ActivateBusinessPayload) => void;
}) {
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 w-full max-w-md bg-card border-l border-border shadow-soft p-5 overflow-y-auto space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="ui-section-title">Стать бизнесом</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Укажите данные компании. Оффер создадите отдельно в разделе «Офферы».
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <BecomeBusinessForm defaults={defaults} pending={pending} onSubmit={onSubmit} />
        <Button variant="secondary" className="w-full" onClick={onClose} disabled={pending}>
          Отмена
        </Button>
      </aside>
    </div>
  );
}
