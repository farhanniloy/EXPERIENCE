import { ExperienceEditor } from "@/components/host/experience-editor";

export const instant = false;

type Props = { params: Promise<{ id: string }> };

export default async function EditExperiencePage({ params }: Props) {
  const { id } = await params;
  return <ExperienceEditor mode="edit" experienceId={id} />;
}
