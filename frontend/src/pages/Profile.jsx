import React, { useEffect, useState } from "react";
import { Plus, ShieldCheck, Trash, UserCircle, UsersThree } from "@phosphor-icons/react";
import { toast } from "sonner";
import api from "../api";


const FIELDS = [
  { key: "weight", label: "Kilo", placeholder: "örn: 97 kg" },
  { key: "target_weight", label: "Hedef Kilo", placeholder: "örn: 85-90 kg" },
  { key: "shoe_size", label: "Kişisel ayakkabı notu", placeholder: "örn: koşuda 44, günlükte 43" },
  { key: "foot_notes", label: "Ayak Yapısı", placeholder: "örn: taraklı ayak, yanlardan sıkma problemi" },
  { key: "usage", label: "Kullanım Amacı", placeholder: "örn: tempolu yürüyüş, asfalt ve orman" },
  { key: "priorities", label: "Öncelikler", placeholder: "örn: yastıklama ve dayanıklılık" },
];

export const PRODUCT_CATEGORIES = [
  { value: "shoes", label: "Ayakkabı", sizeLabel: "Numara", system: "EU" },
  { value: "tops", label: "Tişört / Üst giyim", sizeLabel: "Beden", system: "INT" },
  { value: "pants", label: "Pantolon", sizeLabel: "Beden", system: "WAIST_LENGTH" },
  { value: "outerwear", label: "Dış giyim", sizeLabel: "Beden", system: "INT" },
  { value: "kids", label: "Çocuk giyim", sizeLabel: "Beden", system: "AGE_HEIGHT" },
  { value: "other", label: "Diğer", sizeLabel: "Ölçü / Beden", system: "OTHER" },
];

const SIZE_SYSTEMS = [
  ["EU", "EU numara"],
  ["INT", "S / M / L / XL"],
  ["WAIST_LENGTH", "Bel / paça (32/32)"],
  ["AGE_HEIGHT", "Yaş / boy"],
  ["OTHER", "Diğer"],
];

const makeId = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function splitSizes(value) {
  return [...new Set(String(value || "").split(",").map((item) => item.trim()).filter(Boolean))];
}

function hydrateMembers(rows) {
  return (rows || []).map((member) => ({
    ...member,
    preferences: (member.preferences || []).map((preference) => ({
      ...preference,
      sizes_text: (preference.sizes || []).join(", "),
    })),
  }));
}

function emptyPreference() {
  return {
    id: makeId("preference"),
    category: "shoes",
    label: "Ayakkabı",
    size_system: "EU",
    sizes: [],
    sizes_text: "",
    notes: "",
  };
}

export default function Profile() {
  const [profile, setProfile] = useState({ household_members: [] });
  const [privacy, setPrivacy] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.get("/profile"), api.get("/privacy")]).then(([profileResponse, privacyResponse]) => {
      const next = profileResponse.data || {};
      setProfile({ ...next, household_members: hydrateMembers(next.household_members) });
      setPrivacy(privacyResponse.data);
    });
  }, []);

  const updateMembers = (updater) => {
    setProfile((current) => ({ ...current, household_members: updater(current.household_members || []) }));
  };

  const addMember = () => {
    updateMembers((members) => [
      ...members,
      { id: makeId("member"), name: "", relationship: "", preferences: [emptyPreference()] },
    ]);
  };

  const updateMember = (memberId, changes) => {
    updateMembers((members) => members.map((member) => (
      member.id === memberId ? { ...member, ...changes } : member
    )));
  };

  const removeMember = (memberId) => {
    updateMembers((members) => members.filter((member) => member.id !== memberId));
  };

  const addPreference = (memberId) => {
    updateMembers((members) => members.map((member) => (
      member.id === memberId
        ? { ...member, preferences: [...(member.preferences || []), emptyPreference()] }
        : member
    )));
  };

  const updatePreference = (memberId, preferenceId, changes) => {
    updateMembers((members) => members.map((member) => (
      member.id === memberId
        ? {
            ...member,
            preferences: (member.preferences || []).map((preference) => (
              preference.id === preferenceId ? { ...preference, ...changes } : preference
            )),
          }
        : member
    )));
  };

  const removePreference = (memberId, preferenceId) => {
    updateMembers((members) => members.map((member) => (
      member.id === memberId
        ? { ...member, preferences: (member.preferences || []).filter((item) => item.id !== preferenceId) }
        : member
    )));
  };

  const save = async () => {
    setBusy(true);
    try {
      const body = {};
      FIELDS.forEach((field) => { body[field.key] = profile[field.key] || ""; });
      body.notes = profile.notes || "";
      body.share_profile_with_ai = Boolean(profile.share_profile_with_ai);
      body.household_members = (profile.household_members || [])
        .filter((member) => member.name.trim())
        .map((member) => ({
          id: member.id,
          name: member.name.trim(),
          relationship: member.relationship || "",
          preferences: (member.preferences || []).map(({ sizes_text, ...preference }) => ({
            ...preference,
            sizes: splitSizes(sizes_text),
          })).filter((preference) => preference.sizes.length > 0),
        }));
      const { data } = await api.put("/profile", body);
      setProfile({ ...data, household_members: hydrateMembers(data.household_members) });
      toast.success("Profil ve aile bedenleri kaydedildi");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Profil kaydedilemedi");
    } finally {
      setBusy(false);
    }
  };

  const clearHistory = async () => {
    if (!window.confirm("AI Koç konuşma geçmişinin tamamı silinsin mi?")) return;
    const { data } = await api.delete("/ai/coach/history");
    toast.success(`${data.deleted} konuşma kaydı silindi`);
  };

  return (
    <div className="space-y-6 max-w-4xl" data-testid="profile-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Kişiselleştirme</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Kullanıcı ve Aile Profili</h1>
      </div>

      <div className="card p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FIELDS.map((field) => (
            <div key={field.key}>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">{field.label}</label>
              <input
                data-testid={`profile-${field.key}-input`}
                className="input-dark mt-1"
                placeholder={field.placeholder}
                value={profile[field.key] || ""}
                onChange={(event) => setProfile({ ...profile, [field.key]: event.target.value })}
              />
            </div>
          ))}
        </div>
        <div>
          <label className="text-xs text-zinc-500 uppercase tracking-wider">Ek Notlar</label>
          <textarea
            data-testid="profile-notes-input"
            className="input-dark mt-1 min-h-[80px]"
            placeholder="Diğer tercihler ve geçmiş ürün deneyimleri"
            value={profile.notes || ""}
            onChange={(event) => setProfile({ ...profile, notes: event.target.value })}
          />
        </div>
      </div>

      <section className="card p-6 space-y-5" data-testid="household-size-profiles">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-heading text-xl font-semibold flex items-center gap-2">
              <UsersThree size={22} className="text-primary" /> Aile Beden Profilleri
            </h2>
            <p className="text-sm text-zinc-500 mt-1">
              Her kişi için aynı ürün sınıfında normal beden ve alternatif bedeni birlikte yazabilirsiniz.
            </p>
          </div>
          <button type="button" className="btn-secondary flex items-center gap-2" onClick={addMember}>
            <Plus size={15} /> Kişi Ekle
          </button>
        </div>

        {(profile.household_members || []).length === 0 && (
          <div className="border-y border-zinc-800 py-6 text-sm text-zinc-500">
            Henüz aile profili yok. Örneğin “Ayşe — Ayakkabı — 38, 39” şeklinde ekleyebilirsiniz.
          </div>
        )}

        {(profile.household_members || []).map((member, memberIndex) => (
          <div key={member.id} className="border border-zinc-800 rounded-lg p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
              <div>
                <label className="text-xs text-zinc-500 uppercase tracking-wider">Kişi adı</label>
                <input
                  className="input-dark mt-1"
                  data-testid={`household-member-name-${memberIndex}`}
                  placeholder="Ayşe"
                  value={member.name}
                  onChange={(event) => updateMember(member.id, { name: event.target.value })}
                />
              </div>
              <div>
                <label className="text-xs text-zinc-500 uppercase tracking-wider">Yakınlık / kısa not</label>
                <input
                  className="input-dark mt-1"
                  placeholder="Eşim, çocuğum, kendim"
                  value={member.relationship || ""}
                  onChange={(event) => updateMember(member.id, { relationship: event.target.value })}
                />
              </div>
              <button
                type="button"
                className="h-10 w-10 border border-zinc-800 rounded flex items-center justify-center text-zinc-500 hover:text-red-400"
                title="Kişiyi sil"
                onClick={() => removeMember(member.id)}
              >
                <Trash size={15} />
              </button>
            </div>

            {(member.preferences || []).map((preference, preferenceIndex) => {
              const category = PRODUCT_CATEGORIES.find((item) => item.value === preference.category) || PRODUCT_CATEGORIES[5];
              return (
                <div key={preference.id} className="bg-zinc-950/40 border-y border-zinc-800 py-3 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr_1.5fr_auto] gap-3 items-end">
                    <div>
                      <label className="text-xs text-zinc-500 uppercase tracking-wider">Ürün sınıfı</label>
                      <select
                        className="input-dark mt-1"
                        value={preference.category}
                        onChange={(event) => {
                          const next = PRODUCT_CATEGORIES.find((item) => item.value === event.target.value);
                          updatePreference(member.id, preference.id, {
                            category: next.value,
                            label: next.label,
                            size_system: next.system,
                          });
                        }}
                      >
                        {PRODUCT_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 uppercase tracking-wider">Ölçü sistemi</label>
                      <select
                        className="input-dark mt-1"
                        value={preference.size_system}
                        onChange={(event) => updatePreference(member.id, preference.id, { size_system: event.target.value })}
                      >
                        {SIZE_SYSTEMS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-500 uppercase tracking-wider">{category.sizeLabel} seçenekleri</label>
                      <input
                        className="input-dark mt-1"
                        data-testid={`household-preference-sizes-${memberIndex}-${preferenceIndex}`}
                        placeholder={preference.category === "shoes" ? "42, 43" : preference.category === "pants" ? "32/32, 34/32" : "M, L"}
                        value={preference.sizes_text || ""}
                        onChange={(event) => updatePreference(member.id, preference.id, { sizes_text: event.target.value })}
                      />
                    </div>
                    <button
                      type="button"
                      className="h-10 w-10 border border-zinc-800 rounded flex items-center justify-center text-zinc-500 hover:text-red-400"
                      title="Beden profilini sil"
                      onClick={() => removePreference(member.id, preference.id)}
                    >
                      <Trash size={15} />
                    </button>
                  </div>
                  <input
                    className="input-dark"
                    placeholder="İsteğe bağlı not: Bu model dar kalırsa büyük bedeni tercih et"
                    value={preference.notes || ""}
                    onChange={(event) => updatePreference(member.id, preference.id, { notes: event.target.value })}
                  />
                </div>
              );
            })}

            <button type="button" className="text-xs text-primary flex items-center gap-1" onClick={() => addPreference(member.id)}>
              <Plus size={13} /> Bu kişi için ürün sınıfı ekle
            </button>
          </div>
        ))}

        <div className="text-xs text-zinc-500 border-y border-zinc-800 py-3">
          Bu bilgiler Radar eşleştirmesinde yerel olarak kullanılır. Bir kişi için “42, 43” gibi birden fazla seçenek girilebilir.
        </div>
      </section>

      <div className="card p-6 space-y-4">
        <label className="flex items-start gap-3 border-y border-zinc-800 py-4 cursor-pointer">
          <input
            type="checkbox"
            className="accent-[#CCFF00] w-4 h-4 mt-0.5"
            checked={Boolean(profile.share_profile_with_ai)}
            onChange={(event) => setProfile({ ...profile, share_profile_with_ai: event.target.checked })}
          />
          <span>
            <span className="text-sm flex items-center gap-2"><ShieldCheck size={16} className="text-primary" /> Profilimi AI sağlayıcısıyla paylaş</span>
            <span className="text-xs text-zinc-500 block mt-1">Kapalıyken kişisel ve aile beden bilgileri harici AI hizmetlerine gönderilmez.</span>
          </span>
        </label>
        <button data-testid="profile-save-button" className="btn-primary flex items-center gap-2" onClick={save} disabled={busy}>
          <UserCircle size={16} /> Profili ve Aile Bedenlerini Kaydet
        </button>
      </div>

      <div className="border-y border-zinc-800 py-5 space-y-3">
        <div className="text-sm font-medium">AI Gizliliği</div>
        <div className="flex flex-wrap gap-2">
          {(privacy?.providers || []).map((provider) => (
            <span key={provider.name} className="text-xs font-mono border border-zinc-800 rounded px-2.5 py-1">
              {provider.name}: <span className={provider.configured ? "text-primary" : "text-zinc-600"}>{provider.configured ? "hazır" : "kapalı"}</span>
            </span>
          ))}
        </div>
        <div className="text-xs text-zinc-500">Konuşma geçmişi {privacy?.history_retention_days || 30} gün tutulur.</div>
        <button className="btn-secondary flex items-center gap-2" onClick={clearHistory}>
          <Trash size={15} /> AI Geçmişini Sil
        </button>
      </div>
    </div>
  );
}
