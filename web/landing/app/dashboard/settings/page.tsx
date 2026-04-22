import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "帳號設定 — Symcio Dashboard",
};

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?next=/dashboard/settings");

  const { data: member } = await supabase
    .from("members")
    .select("display_name, email, company_name, title, plan, created_at")
    .eq("id", user.id)
    .maybeSingle();

  const rows = [
    { label: "Email", value: member?.email || user.email || "—" },
    { label: "顯示名稱", value: member?.display_name || "—" },
    { label: "公司", value: member?.company_name || "—" },
    { label: "職稱", value: member?.title || "—" },
    {
      label: "方案",
      value: (member?.plan || "free").toUpperCase(),
    },
    {
      label: "加入時間",
      value: member?.created_at
        ? new Date(member.created_at).toLocaleString("zh-TW")
        : "—",
    },
    { label: "使用者 ID", value: user.id },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold">帳號設定</h2>
        <p className="mt-1 text-sm text-muted">
          目前僅顯示基本資訊；編輯功能在下一版開放。
        </p>
      </div>

      <div className="rounded-card border border-line bg-surface">
        <dl className="divide-y divide-line">
          {rows.map((r) => (
            <div
              key={r.label}
              className="grid grid-cols-3 items-center gap-4 px-6 py-4"
            >
              <dt className="font-mono text-[11px] uppercase tracking-[1.5px] text-muted">
                {r.label}
              </dt>
              <dd className="col-span-2 break-all text-sm text-white">
                {r.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="rounded-card border border-line bg-surface p-6">
        <h3 className="text-lg font-bold">危險區</h3>
        <p className="mt-2 text-sm text-muted">
          忘記密碼或要刪除帳號？請寫信到{" "}
          <a
            href="mailto:info@symcio.tw"
            className="text-accent no-underline"
          >
            info@symcio.tw
          </a>
          ，我們會在 24 小時內處理。刪除後所有 BCI 歷史與設定將永久消失。
        </p>
      </div>
    </div>
  );
}
