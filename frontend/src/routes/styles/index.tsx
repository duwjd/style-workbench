import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { stylesApi } from "@/api/styles";
import { StyleList } from "@/features/styles/StyleList";

export default function StylesPage() {
  const navigate = useNavigate();
  const { data: styles, isLoading } = useQuery({
    queryKey: ["styles"],
    queryFn: stylesApi.getAll,
  });

  return (
    <StyleList
      styles={styles ?? []}
      isLoading={isLoading}
      onNew={() => navigate("/styles/new")}
      onSelect={(id) => navigate(`/styles/${id}`)}
    />
  );
}
