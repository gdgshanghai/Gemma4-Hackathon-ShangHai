import { useState, useRef, useEffect, type ReactNode } from "react";

export function AccordionSection({
	title,
	badge,
	defaultOpen = false,
	children,
}: {
	title: string;
	badge?: string | number;
	defaultOpen?: boolean;
	children: ReactNode;
}) {
	const [open, setOpen] = useState(defaultOpen);
	const bodyRef = useRef<HTMLDivElement>(null);
	const [height, setHeight] = useState<number | undefined>(
		defaultOpen ? undefined : 0,
	);

	useEffect(() => {
		if (!bodyRef.current) return;
		if (open) {
			setHeight(bodyRef.current.scrollHeight);
			// After transition, switch to auto so content can resize
			const t = setTimeout(() => setHeight(undefined), 250);
			return () => clearTimeout(t);
		}
		// Collapse: set explicit height first, then 0 on next frame
		setHeight(bodyRef.current.scrollHeight);
		requestAnimationFrame(() => setHeight(0));
	}, [open]);

	return (
		<div
			style={{
				borderBottom: "1px solid var(--color-border-primary)",
			}}
		>
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				style={{
					display: "flex",
					alignItems: "center",
					justifyContent: "space-between",
					width: "100%",
					padding: "8px 12px",
					background: "var(--color-bg-secondary)",
					border: "none",
					borderBottom: open
						? "1px solid var(--color-border-primary)"
						: "1px solid transparent",
					cursor: "pointer",
					fontSize: 11,
					fontWeight: 600,
					textTransform: "uppercase",
					letterSpacing: "0.08em",
					color: "var(--color-text-secondary)",
					fontFamily: "inherit",
					userSelect: "none",
				}}
			>
				<div style={{ display: "flex", alignItems: "center", gap: 8 }}>
					<span
						style={{
							fontSize: 8,
							transition: "transform 0.2s ease",
							transform: open ? "rotate(90deg)" : "rotate(0deg)",
							display: "inline-block",
						}}
					>
						▶
					</span>
					<span>{title}</span>
				</div>
				{badge !== undefined && (
					<span style={{ color: "var(--color-text-muted)", fontSize: 10 }}>
						{badge}
					</span>
				)}
			</button>
			<div
				ref={bodyRef}
				style={{
					overflow: "hidden",
					height: height === undefined ? "auto" : height,
					transition: "height 0.25s ease",
				}}
			>
				<div style={{ padding: 8 }}>{children}</div>
			</div>
		</div>
	);
}
