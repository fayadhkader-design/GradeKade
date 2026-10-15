import CorrectionWorkspace from "@/components/CorrectionWorkspace";
export default async function CorrectionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CorrectionWorkspace id={id} />;
}
