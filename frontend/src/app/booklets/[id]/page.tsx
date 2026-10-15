import BookletResults from "@/components/BookletResults";
export default async function BookletPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BookletResults id={id} />;
}
