import { useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { stylesApi } from "@/api/styles";
import { StyleBuilder } from "@/features/style-builder/StyleBuilder";

export default function StyleBuilderPage() {
  const { styleId } = useParams<{ styleId: string }>();
  const { data: style, isLoading, isError } = useQuery({
    queryKey: ["styles", styleId],
    queryFn: () => stylesApi.getById(styleId!),
    enabled: !!styleId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-text-secondary text-sm">로딩 중...</span>
      </div>
    );
  }

  if (isError || !style) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-error text-sm">Style을 찾을 수 없습니다.</span>
      </div>
    );
  }

  return <StyleBuilder style={style} />;
}
