import { BookingFlow } from "@/components/booking/booking-flow";

export const instant = false;

type Props = { params: Promise<{ slug: string }> };

export default async function BookExperiencePage({ params }: Props) {
  const { slug } = await params;
  return <BookingFlow slug={slug} />;
}
