import { BookingDetail } from "@/components/booking/booking-detail";

export const instant = false;

type Props = { params: Promise<{ bookingId: string }> };

export default async function BookingDetailPage({ params }: Props) {
  const { bookingId } = await params;
  return <BookingDetail bookingId={bookingId} />;
}
