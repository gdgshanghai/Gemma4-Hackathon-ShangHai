import type { Object3DNode } from "@react-three/fiber";
import type { ThreeElements } from "@react-three/fiber";
import type { Line } from "three";

declare module "react" {
	namespace JSX {
		interface IntrinsicElements extends ThreeElements {
			line_: Object3DNode<Line, typeof Line>;
		}
	}
}
