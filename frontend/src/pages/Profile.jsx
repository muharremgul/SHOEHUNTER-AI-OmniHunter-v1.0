import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { UserCircle } from "@phosphor-icons/react";
import api from "../api";

const FIELDS = [
  { key: "weight", label: "Kilo", placeholder: "örn: 97 kg" },
  { key: "target_weight", label: "Hedef Kilo", placeholder: "örn: 85-90 kg" },
  { key: "shoe_size", label: "Ayakkabı Numarası", placeholder: "örn: EU 43, bazen 44" },
  { key: "foot_notes", label: "Ayak Yapısı", placeholder: "örn: taraklı ayak, yanlardan sıkma problemi" },
  { key: "usage", label: "Kullanım Amacı", placeholder: "örn: tempolu yürüyüş, asfalt + orman" },
  { key: "priorities", label: "Öncelikler", placeholder: "örn: yastıklama ve dayanıklılık" },
];

export default function Profile() {
  const [profile, setProfile] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/profile").then((r) => setProfile(r.data || {}));
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      const body = {};
      FIELDS.forEach((f) => (body[f.key] = profile[f.key] || ""));
      body.notes = profile.notes || "";
      await api.put("/profile", body);
      toast.success("Profil kaydedildi. AI Koç artık bu bilgileri dikkate alacak.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl" data-testid="profile-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-primary font-mono">Kişiselleştirme</div>
        <h1 className="text-4xl font-heading font-bold tracking-tighter mt-1">Kullanıcı Profili</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Bu bilgiler AI Koç önerilerinde kullanılır: kalıp uyarısı, dayanıklılık yorumu, beden tavsiyesi.
        </p>
      </div>

      <div className="card p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FIELDS.map((f) => (
            <div key={f.key}>
              <label className="text-xs text-zinc-500 uppercase tracking-wider">{f.label}</label>
              <input
                data-testid={`profile-${f.key}-input`}
                className="input-dark mt-1"
                placeholder={f.placeholder}
                value={profile[f.key] || ""}
                onChange={(e) => setProfile({ ...profile, [f.key]: e.target.value })}
              />
            </div>
          ))}
        </div>
        <div>
          <label className="text-xs text-zinc-500 uppercase tracking-wider">Ek Notlar</label>
          <textarea
            data-testid="profile-notes-input"
            className="input-dark mt-1 min-h-[80px]"
            placeholder="Diğer tercihler, geçmiş ayakkabı deneyimleri..."
            value={profile.notes || ""}
            onChange={(e) => setProfile({ ...profile, notes: e.target.value })}
          />
        </div>
        <button data-testid="profile-save-button" className="btn-primary flex items-center gap-2" onClick={save} disabled={busy}>
          <UserCircle size={16} /> Profili Kaydet
        </button>
      </div>
    </div>
  );
}
