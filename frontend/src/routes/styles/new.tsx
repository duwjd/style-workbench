import { useState } from "react";
import { useNavigate } from "react-router";
import { BriefForm } from "@/features/variants/BriefForm";
import { VariantPicker } from "@/features/variants/VariantPicker";
import type { StyleSummary } from "@/types";

export default function NewStylePage() {
  const navigate = useNavigate();
  const [variants, setVariants] = useState<StyleSummary[] | null>(null);

  if (variants) {
    return (
      <VariantPicker
        variants={variants}
        onSelect={(id) => navigate(`/styles/${id}`)}
      />
    );
  }

  return <BriefForm onSuccess={setVariants} />;
}
