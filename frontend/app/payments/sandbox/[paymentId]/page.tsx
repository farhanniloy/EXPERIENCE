import { SandboxPayment } from "@/components/payments/sandbox-payment";

export const instant = false;

type Props = { params: Promise<{ paymentId: string }> };

export default async function SandboxPaymentPage({ params }: Props) {
  const { paymentId } = await params;
  return <SandboxPayment paymentId={paymentId} />;
}
