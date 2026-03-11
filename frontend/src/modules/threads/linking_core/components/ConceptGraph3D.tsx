/**
 * ConceptGraph3D - 3D Neural Nebula Visualization
 * ================================================
 * A contained purple nebula sphere with concept nodes inside.
 * 
 * The purple gas swirls as a bounding "containment field"
 * Silver/gold nodes float inside representing concepts
 * Lightning arcs between nodes show activation spreading
 * 
 * This is the visual representation of the agent's associative memory.
 * "Attention over concepts, not tokens" - made visible.
 */

import { useRef, useState, useEffect, useMemo, useCallback } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Text, Sphere, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

// ============================================================================
// Fly Controls - WASD + Mouse for spaceship-style navigation
// ============================================================================

interface FlyControlsProps {
  moveSpeed?: number;
  lookSpeed?: number;
}

function FlyControls({ moveSpeed = 3, lookSpeed = 0.002 }: FlyControlsProps) {
  const { camera, gl } = useThree();
  const keysPressed = useRef<Set<string>>(new Set());
  const isMouseDown = useRef(false);
  const euler = useRef(new THREE.Euler(0, 0, 0, 'YXZ'));
  
  useEffect(() => {
    // Initialize euler from camera
    euler.current.setFromQuaternion(camera.quaternion);
    
    const handleKeyDown = (e: KeyboardEvent) => {
      keysPressed.current.add(e.code.toLowerCase());
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      keysPressed.current.delete(e.code.toLowerCase());
    };
    const handleMouseDown = (e: MouseEvent) => {
      if (e.button === 0 || e.button === 2) {
        isMouseDown.current = true;
      }
    };
    const handleMouseUp = () => {
      isMouseDown.current = false;
    };
    const handleMouseMove = (e: MouseEvent) => {
      if (!isMouseDown.current) return;
      
      euler.current.y -= e.movementX * lookSpeed;
      euler.current.x -= e.movementY * lookSpeed;
      euler.current.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.current.x));
      
      camera.quaternion.setFromEuler(euler.current);
    };
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      // Zoom moves camera forward/backward in look direction
      // Much faster zoom for deep exploration
      const direction = new THREE.Vector3();
      camera.getWorldDirection(direction);
      // Use deltaY for scroll wheel, also handle pinch zoom (deltaY on trackpad)
      const delta = e.deltaY !== 0 ? e.deltaY : e.deltaX;
      camera.position.addScaledVector(direction, -delta * 0.05);
    };
    const handleContextMenu = (e: Event) => e.preventDefault();
    
    const domElement = gl.domElement;
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    domElement.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);
    domElement.addEventListener('mousemove', handleMouseMove);
    // Use passive: false to allow preventDefault on wheel
    domElement.addEventListener('wheel', handleWheel, { passive: false });
    domElement.addEventListener('contextmenu', handleContextMenu);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      domElement.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
      domElement.removeEventListener('mousemove', handleMouseMove);
      domElement.removeEventListener('wheel', handleWheel);
      domElement.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [camera, gl, lookSpeed]);
  
  useFrame((_, delta) => {
    const keys = keysPressed.current;
    // Hold shift for slow/precision movement when close to nodes
    const speedMultiplier = keys.has('shiftleft') || keys.has('shiftright') ? 0.2 : 1;
    const speed = moveSpeed * delta * speedMultiplier;
    const turnSpeed = 1.5 * delta * speedMultiplier;
    
    // Get camera directions
    const forward = new THREE.Vector3();
    const right = new THREE.Vector3();
    camera.getWorldDirection(forward);
    right.crossVectors(forward, camera.up).normalize();
    
    // W/S or Up/Down arrows: move forward/back
    if (keys.has('keyw') || keys.has('arrowup')) {
      camera.position.addScaledVector(forward, speed);
    }
    if (keys.has('keys') || keys.has('arrowdown')) {
      camera.position.addScaledVector(forward, -speed);
    }
    
    // A/D: strafe left/right
    if (keys.has('keya')) {
      camera.position.addScaledVector(right, -speed);
    }
    if (keys.has('keyd')) {
      camera.position.addScaledVector(right, speed);
    }
    
    // Left/Right arrows: turn/rotate camera
    if (keys.has('arrowleft')) {
      euler.current.y += turnSpeed;
      camera.quaternion.setFromEuler(euler.current);
    }
    if (keys.has('arrowright')) {
      euler.current.y -= turnSpeed;
      camera.quaternion.setFromEuler(euler.current);
    }
    
    // Q/E for up/down
    if (keys.has('keyq')) {
      camera.position.y += speed;
    }
    if (keys.has('keye')) {
      camera.position.y -= speed;
    }
    
  });
  
  return null;
}

// ============================================================================
// Types
// ============================================================================

interface ConceptNode {
  id: string;
  label: string;
  connections: number;
  total_strength: number;
  earliest_link?: string;  // Timestamp of first link (temporal origin)
  latest_link?: string;    // Most recent activity
}

interface ConceptLink {
  concept_a: string;
  concept_b: string;
  strength: number;
  fire_count: number;
  last_fired?: string;
}

interface GraphData {
  nodes: ConceptNode[];
  links: ConceptLink[];
  stats: {
    total_links: number;
    avg_strength: number;
    max_strength: number;
    unique_concepts: number;
  };
}

interface ConceptGraph3DProps {
  mode?: 'ambient' | 'live';
  onNodeClick?: (nodeId: string) => void;
  activationQuery?: string;
}

// ── Structural graph types (from /api/linking_core/graph/structural) ──

interface StructuralNode {
  id: string;
  label: string;
  thread: string;   // identity | philosophy | form | reflex | log | linking_core
  kind: string;     // thread | group | fact | tool | trigger | event
  depth: number;    // 0 = thread root, 1 = profile/group, 2 = leaf fact
  weight: number;
  data: Record<string, any>;
}

interface StructuralEdge {
  source: string;
  target: string;
  type: 'structural' | 'associative';
  strength?: number;
  fire_count?: number;
  cross_thread?: boolean;
}

interface StructuralGraphData {
  nodes: StructuralNode[];
  structural: StructuralEdge[];
  associative: StructuralEdge[];
  stats: {
    node_count: number;
    structural_count: number;
    associative_count: number;
    threads: string[];
  };
}

type ViewMode = 'cluster' | 'structure' | 'cooccurrence';

interface ViewDef {
  id: ViewMode;
  icon: string;
  label: string;
}

const VIEWS: ViewDef[] = [
  { id: 'cluster', icon: '🔮', label: 'Concept Cluster' },
  { id: 'structure', icon: '🧬', label: 'Architecture' },
  { id: 'cooccurrence', icon: '🔗', label: 'Co-occurrence' },
];

// ============================================================================
// Co-occurrence types
// ============================================================================

interface CooccurrencePair {
  key_a: string;
  key_b: string;
  count: number;
  last_seen: string | null;
}

interface CooccurrenceConcept {
  concept: string;
  total_count: number;
}

interface CooccurrenceData {
  pairs: CooccurrencePair[];
  top_concepts: CooccurrenceConcept[];
  stats: {
    total_pairs: number;
    returned: number;
    max_count: number;
  };
}

// Thread color palette
const THREAD_COLORS: Record<string, string> = {
  identity:     '#00ccff',  // cyan
  philosophy:   '#ffcc00',  // gold
  form:         '#00ff88',  // green
  reflex:       '#ff4466',  // coral
  log:          '#8899bb',  // silver
  linking_core: '#cc88ff',  // purple
};

const THREAD_HSL: Record<string, [number, number, number]> = {
  identity:     [0.52, 0.9, 0.55],
  philosophy:   [0.13, 0.9, 0.55],
  form:         [0.42, 0.9, 0.55],
  reflex:       [0.97, 0.85, 0.6],
  log:          [0.6,  0.2, 0.6],
  linking_core: [0.76, 0.6, 0.7],
};

// ============================================================================
// Create circular sprite texture (dots not squares!)
// ============================================================================

function createCircleTexture(): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  
  // Radial gradient for soft circular dot
  const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
  gradient.addColorStop(0.3, 'rgba(255, 255, 255, 0.8)');
  gradient.addColorStop(0.7, 'rgba(255, 255, 255, 0.2)');
  gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
  
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 64, 64);
  
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// ============================================================================
// Nebula Shell - The Purple Containment Sphere
// ============================================================================

interface NebulaShellProps {
  nodePositions?: Map<string, [number, number, number]>;
  nodeConnections?: Map<string, number>;
}

function NebulaShell({ nodePositions, nodeConnections }: NebulaShellProps) {
  const particlesRef = useRef<THREE.Points>(null);
  const innerRef = useRef<THREE.Points>(null);
  const gasRef = useRef<THREE.Points>(null);
  
  // Create circle texture once
  const circleTexture = useMemo(() => createCircleTexture(), []);
  
  // Outer swirling shell - follows the shape of the graph
  const outerParticles = useMemo(() => {
    const count = 4000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    // Get node positions array for sampling
    const nodePositionsArray = nodePositions ? Array.from(nodePositions.values()) : [];
    
    for (let i = 0; i < count; i++) {
      let x, y, z;
      
      if (nodePositionsArray.length > 0 && Math.random() < 0.85) {
        // 85% of particles cluster around actual node positions
        const nodePos = nodePositionsArray[Math.floor(Math.random() * nodePositionsArray.length)];
        const nodeDist = Math.sqrt(nodePos[0] ** 2 + nodePos[1] ** 2 + nodePos[2] ** 2);
        
        // Place particles in a shell around/beyond the node
        const offsetRadius = 0.3 + Math.random() * 0.8; // Shell offset from node
        
        // Direction from center through node, then add offset
        const nodeDir = new THREE.Vector3(nodePos[0], nodePos[1], nodePos[2]).normalize();
        const shellDist = nodeDist + offsetRadius;
        
        // Add some tangential spread
        const tangentOffset = new THREE.Vector3(
          (Math.random() - 0.5) * 0.6,
          (Math.random() - 0.5) * 0.6,
          (Math.random() - 0.5) * 0.6
        );
        
        x = nodeDir.x * shellDist + tangentOffset.x;
        y = nodeDir.y * shellDist + tangentOffset.y;
        z = nodeDir.z * shellDist + tangentOffset.z;
      } else {
        // 15% random spherical distribution for fill
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = Math.random() * Math.PI * 2;
        const radius = 2.5 + Math.random() * 2.5; // Varied radius
        
        x = radius * Math.sin(phi) * Math.cos(theta);
        y = radius * Math.sin(phi) * Math.sin(theta);
        z = radius * Math.cos(phi);
      }
      
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      
      // Purple/magenta gradient
      const hue = 0.75 + Math.random() * 0.15; // Purple range
      const sat = 0.6 + Math.random() * 0.4;
      const light = 0.3 + Math.random() * 0.4;
      const color = new THREE.Color().setHSL(hue, sat, light);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    
    return { positions, colors };
  }, [nodePositions]);
  
  // Wispy gas that concentrates near high-density areas (nodes with many connections)
  const gasParticles = useMemo(() => {
    const count = 2000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    
    // Build density map from node positions
    const densityPoints: Array<{ pos: [number, number, number]; weight: number }> = [];
    if (nodePositions && nodeConnections) {
      nodePositions.forEach((pos, id) => {
        const connections = nodeConnections.get(id) || 1;
        densityPoints.push({ pos, weight: Math.log10(connections + 1) });
      });
    }
    
    for (let i = 0; i < count; i++) {
      let x: number, y: number, z: number;
      let density = 0.1;
      
      if (densityPoints.length > 0 && Math.random() < 0.7) {
        // 70% of gas particles cluster near high-connection nodes
        const weightedRandom = densityPoints[Math.floor(Math.random() * densityPoints.length)];
        const spread = 0.8 + Math.random() * 0.5;
        x = weightedRandom.pos[0] + (Math.random() - 0.5) * spread;
        y = weightedRandom.pos[1] + (Math.random() - 0.5) * spread;
        z = weightedRandom.pos[2] + (Math.random() - 0.5) * spread;
        density = 0.2 + weightedRandom.weight * 0.15;
      } else {
        // 30% distributed randomly for atmosphere
        const phi = Math.acos(2 * Math.random() - 1);
        const theta = Math.random() * Math.PI * 2;
        const radius = Math.random() * 3;
        x = radius * Math.sin(phi) * Math.cos(theta);
        y = radius * Math.sin(phi) * Math.sin(theta);
        z = radius * Math.cos(phi);
      }
      
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      
      // Wispy purple-pink color
      const hue = 0.78 + Math.random() * 0.1;
      const color = new THREE.Color().setHSL(hue, 0.4 + Math.random() * 0.3, 0.5 + density * 0.3);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
      
      sizes[i] = 0.1 + density * 0.15;
    }
    
    return { positions, colors, sizes };
  }, [nodePositions, nodeConnections]);
  
  // Inner spiral wisps
  const innerParticles = useMemo(() => {
    const count = 1200;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    for (let i = 0; i < count; i++) {
      // Spiral distribution inside
      const t = i / count;
      const angle = t * Math.PI * 8;
      const radius = t * 2.5;
      const height = (Math.random() - 0.5) * 2;
      
      positions[i * 3] = Math.cos(angle) * radius + (Math.random() - 0.5) * 0.5;
      positions[i * 3 + 1] = height;
      positions[i * 3 + 2] = Math.sin(angle) * radius + (Math.random() - 0.5) * 0.5;
      
      // Lighter purple for inner wisps
      colors[i * 3] = 0.6 + Math.random() * 0.2;
      colors[i * 3 + 1] = 0.3 + Math.random() * 0.2;
      colors[i * 3 + 2] = 0.8 + Math.random() * 0.2;
    }
    
    return { positions, colors };
  }, []);
  
  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y += 0.0008;
      particlesRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1;
    }
    if (innerRef.current) {
      innerRef.current.rotation.y -= 0.002;
      innerRef.current.rotation.z = Math.cos(state.clock.elapsedTime * 0.15) * 0.05;
    }
    if (gasRef.current) {
      // Very slow drift for the gas
      gasRef.current.rotation.y += 0.0003;
      gasRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.05) * 0.02;
    }
  });
  
  return (
    <>
      {/* Density gas layer - thin wispy atmosphere */}
      <points ref={gasRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[gasParticles.positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[gasParticles.colors, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.15}
          map={circleTexture}
          vertexColors
          transparent
          opacity={0.12}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          sizeAttenuation={true}
        />
      </points>
      
      {/* Outer shell */}
      <points ref={particlesRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[outerParticles.positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[outerParticles.colors, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.06}
          map={circleTexture}
          vertexColors
          transparent
          opacity={0.7}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          sizeAttenuation={true}
        />
      </points>
      
      {/* Inner wisps */}
      <points ref={innerRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[innerParticles.positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[innerParticles.colors, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.04}
          map={circleTexture}
          vertexColors
          transparent
          opacity={0.35}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          sizeAttenuation={true}
        />
      </points>
      
      {/* Glowing core */}
      <Sphere args={[0.3, 32, 32]} position={[0, 0, 0]}>
        <meshBasicMaterial color="#cc88ff" transparent opacity={0.25} />
      </Sphere>
      <Sphere args={[0.12, 16, 16]} position={[0, 0, 0]}>
        <meshBasicMaterial color="#ffffff" transparent opacity={0.5} />
      </Sphere>
    </>
  );
}

// ============================================================================
// Concept Node - Floating Orbs Inside the Nebula
// ============================================================================

interface NodeProps {
  position: [number, number, number];
  node: ConceptNode;
  isActivated: boolean;
  activationLevel: number;
  onClick?: () => void;
  showLabel: boolean;
  isOrigin?: boolean;
  age?: number;  // 0 = oldest (temporal origin), 1 = newest
}

function ConceptNodeMesh({ position, node, isActivated, activationLevel, onClick, showLabel, isOrigin, age = 0.5 }: NodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  
  // Size based on connections - logarithmic scaling for dramatic difference
  // Origin node is always larger
  const logConnections = Math.log10(Math.max(node.connections, 1) + 1);
  const baseSize = isOrigin ? 0.12 : 0.02 + logConnections * 0.04;
  const size = hovered ? baseSize * 1.8 : baseSize;
  
  useFrame((state) => {
    if (meshRef.current) {
      // Origin stays fixed, others float gently
      if (!isOrigin) {
        meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime + position[0]) * 0.05;
      }
      
      // Pulse when activated (or always for origin)
      if ((isActivated || isOrigin) && glowRef.current) {
        const pulseSpeed = isOrigin ? 1.5 : 5;
        const pulseAmount = isOrigin ? 0.15 : 0.3 * activationLevel;
        const pulse = 1 + Math.sin(state.clock.elapsedTime * pulseSpeed) * pulseAmount;
        glowRef.current.scale.setScalar(pulse);
      }
    }
  });
  
  // Color based on age and activation - staying in purple/blue/white/silver theme
  // Older concepts = deeper purple (0.75 hue)
  // Newer concepts = lighter silver/white (higher lightness)
  // Origin is special warm white
  const nodeColor = isOrigin
    ? new THREE.Color().setHSL(0.72, 0.3, 0.9) // Soft white with slight purple
    : isActivated 
      ? new THREE.Color().setHSL(0.7, 0.7, 0.7 + activationLevel * 0.2) // Bright purple-white when active
      : new THREE.Color().setHSL(
          0.72 + age * 0.08, // Purple (0.72) to blue (0.60) based on age
          0.3 + (1 - age) * 0.4, // Older = more saturated purple
          0.5 + age * 0.35 // Newer = lighter/whiter
        );
  
  const glowColor = isOrigin
    ? new THREE.Color().setHSL(0.75, 0.4, 0.7) // Soft purple-white glow
    : isActivated
      ? new THREE.Color().setHSL(0.7, 0.8, 0.6) // Bright purple glow
      : new THREE.Color().setHSL(0.75, 0.5, 0.4 + age * 0.2); // Purple glow, lighter for newer
  
  return (
    <group position={position}>
      {/* Main node */}
      <mesh
        ref={meshRef}
        onClick={onClick}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[size, 16, 16]} />
        <meshStandardMaterial
          color={nodeColor}
          emissive={nodeColor}
          emissiveIntensity={isActivated ? 0.5 : 0.15}
          metalness={0.6}
          roughness={0.3}
        />
      </mesh>
      
      {/* Glow sphere */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[size * 2, 16, 16]} />
        <meshBasicMaterial
          color={glowColor}
          transparent
          opacity={isActivated ? 0.4 : 0.1}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      
      {/* Label */}
      {(showLabel || hovered || isActivated) && (
        <Text
          position={[0, size + 0.12, 0]}
          fontSize={0.08}
          color={isActivated ? '#ffdd66' : hovered ? '#ffffff' : '#aaaacc'}
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.004}
          outlineColor="#000000"
        >
          {node.label.length > 20 ? node.label.slice(0, 20) + '…' : node.label}
        </Text>
      )}
      {/* Strength info on hover */}
      {hovered && (
        <Text
          position={[0, size + 0.04, 0]}
          fontSize={0.05}
          color="#aa88cc"
          anchorX="center"
          anchorY="top"
          outlineWidth={0.003}
          outlineColor="#000000"
        >
          {`s=${node.total_strength?.toFixed(2) ?? '?'}  c=${node.connections}`}
        </Text>
      )}
    </group>
  );
}

// ============================================================================
// Energy Arc - Connection Visualization
// ============================================================================

interface ArcProps {
  start: [number, number, number];
  end: [number, number, number];
  strength: number;
  isActive: boolean;
}

function EnergyArc({ start, end, strength, isActive }: ArcProps) {
  // Create curved path
  const curve = useMemo(() => {
    const mid: [number, number, number] = [
      (start[0] + end[0]) / 2,
      (start[1] + end[1]) / 2 + 0.3,
      (start[2] + end[2]) / 2,
    ];
    return new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...start),
      new THREE.Vector3(...mid),
      new THREE.Vector3(...end)
    );
  }, [start, end]);
  
  const points = useMemo(() => curve.getPoints(20), [curve]);
  
  const lineObject = useMemo(() => {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: isActive ? new THREE.Color(1, 0.8, 0.3) : new THREE.Color(0.5, 0.3, 0.7),
      transparent: true,
      opacity: isActive ? 0.8 : 0.15 + strength * 0.2,
    });
    return new THREE.Line(geometry, material);
  }, [points, isActive, strength]);
  
  return <primitive object={lineObject} />;
}

// ============================================================================
// Resonance Points - Where strings intersect in space
// ============================================================================

interface ResonancePointsProps {
  links: ConceptLink[];
  nodePositions: Map<string, [number, number, number]>;
}

function ResonancePoints({ links, nodePositions }: ResonancePointsProps) {
  const pointsRef = useRef<THREE.Points>(null);
  
  // Find intersection points between curves
  const intersections = useMemo(() => {
    const points: Array<{ pos: THREE.Vector3; density: number }> = [];
    const curves: THREE.QuadraticBezierCurve3[] = [];
    
    // Build all curves
    for (const link of links.slice(0, 100)) { // Limit for performance
      const startPos = nodePositions.get(link.concept_a);
      const endPos = nodePositions.get(link.concept_b);
      if (!startPos || !endPos) continue;
      if (link.strength < 0.2) continue;
      
      const mid = new THREE.Vector3(
        (startPos[0] + endPos[0]) / 2,
        (startPos[1] + endPos[1]) / 2 + 0.3,
        (startPos[2] + endPos[2]) / 2
      );
      
      curves.push(new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(...startPos),
        mid,
        new THREE.Vector3(...endPos)
      ));
    }
    
    // Sample points along each curve and find close points from different curves
    const threshold = 0.15; // Distance threshold for "intersection"
    const samples = 10; // Points per curve
    
    for (let i = 0; i < curves.length; i++) {
      for (let j = i + 1; j < curves.length; j++) {
        // Sample both curves
        for (let ti = 0.2; ti <= 0.8; ti += 1 / samples) {
          const pi = curves[i].getPoint(ti);
          
          for (let tj = 0.2; tj <= 0.8; tj += 1 / samples) {
            const pj = curves[j].getPoint(tj);
            
            const dist = pi.distanceTo(pj);
            if (dist < threshold) {
              // Found an intersection! Use midpoint
              const intersection = pi.clone().add(pj).multiplyScalar(0.5);
              
              // Check if we already have a point nearby
              const existing = points.find(p => p.pos.distanceTo(intersection) < threshold);
              if (existing) {
                existing.density += 1; // More curves meeting = higher density
              } else {
                points.push({ pos: intersection, density: 1 });
              }
            }
          }
        }
      }
    }
    
    return points;
  }, [links, nodePositions]);
  
  // Create geometry for resonance points
  const { positions, colors } = useMemo(() => {
    const positions = new Float32Array(intersections.length * 3);
    const colors = new Float32Array(intersections.length * 3);
    
    intersections.forEach((point, i) => {
      positions[i * 3] = point.pos.x;
      positions[i * 3 + 1] = point.pos.y;
      positions[i * 3 + 2] = point.pos.z;
      
      // Color based on density - more intersections = brighter/whiter
      const intensity = Math.min(point.density / 5, 1);
      const hue = 0.8 - intensity * 0.2; // Purple to pink/white
      const color = new THREE.Color().setHSL(hue, 0.6 - intensity * 0.4, 0.5 + intensity * 0.4);
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    });
    
    return { positions, colors };
  }, [intersections]);
  
  // Pulse animation
  useFrame((state) => {
    if (pointsRef.current) {
      const material = pointsRef.current.material as THREE.PointsMaterial;
      material.opacity = 0.5 + Math.sin(state.clock.elapsedTime * 2) * 0.2;
    }
  });
  
  if (intersections.length === 0) return null;
  
  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        vertexColors
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation={true}
      />
    </points>
  );
}

// ============================================================================
// Storm Lightning - Small ambient lightning around the nebula edges
// ============================================================================

interface LightningBolt {
  id: number;
  points: THREE.Vector3[];
  startTime: number;
  duration: number;
  opacity: number;
  color: THREE.Color;
}

function StormLightning({ radius = 4 }: { radius?: number }) {
  const [bolts, setBolts] = useState<LightningBolt[]>([]);
  const boltIdRef = useRef(0);
  
  // Generate a jagged lightning bolt path
  const generateBoltPath = useCallback((start: THREE.Vector3, direction: THREE.Vector3, length: number): THREE.Vector3[] => {
    const points: THREE.Vector3[] = [start.clone()];
    const segments = 4 + Math.floor(Math.random() * 4); // 4-7 segments
    const segmentLength = length / segments;
    
    let current = start.clone();
    const dir = direction.clone().normalize();
    
    for (let i = 0; i < segments; i++) {
      // Move in general direction with random jitter
      const jitter = new THREE.Vector3(
        (Math.random() - 0.5) * segmentLength * 0.8,
        (Math.random() - 0.5) * segmentLength * 0.8,
        (Math.random() - 0.5) * segmentLength * 0.8
      );
      
      current = current.clone().add(dir.clone().multiplyScalar(segmentLength)).add(jitter);
      points.push(current.clone());
    }
    
    return points;
  }, []);
  
  // Spawn lightning bolts randomly
  useEffect(() => {
    const spawnBolt = () => {
      // Random position on sphere surface (outer edge of nebula)
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = radius * (0.8 + Math.random() * 0.4); // Slightly varied radius
      
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);
      
      const start = new THREE.Vector3(x, y, z);
      
      // Direction: mostly tangent to sphere surface with some inward/outward
      const radial = start.clone().normalize();
      const tangent1 = new THREE.Vector3(-radial.y, radial.x, 0).normalize();
      const tangent2 = radial.clone().cross(tangent1).normalize();
      
      const direction = tangent1.clone()
        .multiplyScalar(Math.random() - 0.5)
        .add(tangent2.clone().multiplyScalar(Math.random() - 0.5))
        .add(radial.clone().multiplyScalar((Math.random() - 0.5) * 0.3))
        .normalize();
      
      const length = 0.3 + Math.random() * 0.5; // Small bolts
      const points = generateBoltPath(start, direction, length);
      
      const newBolt: LightningBolt = {
        id: boltIdRef.current++,
        points,
        startTime: Date.now(),
        duration: 80 + Math.random() * 120, // 80-200ms flash
        opacity: 0.3 + Math.random() * 0.4, // Subtle
        color: new THREE.Color().setHSL(
          0.7 + Math.random() * 0.15, // Blue to purple
          0.4 + Math.random() * 0.3,
          0.7 + Math.random() * 0.3
        ),
      };
      
      setBolts(prev => [...prev, newBolt]);
    };
    
    // Random spawning - every 100-400ms
    const scheduleNext = () => {
      const delay = 100 + Math.random() * 300;
      return setTimeout(() => {
        spawnBolt();
        scheduleNext();
      }, delay);
    };
    
    const timeout = scheduleNext();
    return () => clearTimeout(timeout);
  }, [radius, generateBoltPath]);
  
  // Clean up expired bolts
  useFrame(() => {
    const now = Date.now();
    setBolts(prev => prev.filter(bolt => now - bolt.startTime < bolt.duration));
  });
  
  return (
    <group>
      {bolts.map(bolt => (
        <LightningBoltMesh key={bolt.id} bolt={bolt} />
      ))}
    </group>
  );
}

function LightningBoltMesh({ bolt }: { bolt: LightningBolt }) {
  const lineRef = useRef<THREE.Line>(null);
  
  // Animate opacity
  useFrame(() => {
    if (!lineRef.current) return;
    
    const elapsed = Date.now() - bolt.startTime;
    const progress = elapsed / bolt.duration;
    
    // Flash in fast, fade out
    let opacity: number;
    if (progress < 0.1) {
      opacity = progress * 10 * bolt.opacity; // Quick flash in
    } else {
      opacity = (1 - progress) * bolt.opacity; // Fade out
    }
    
    const material = lineRef.current.material as THREE.LineBasicMaterial;
    material.opacity = opacity;
  });
  
  const positions = useMemo(() => {
    const arr = new Float32Array(bolt.points.length * 3);
    bolt.points.forEach((p, i) => {
      arr[i * 3] = p.x;
      arr[i * 3 + 1] = p.y;
      arr[i * 3 + 2] = p.z;
    });
    return arr;
  }, [bolt.points]);
  
  return (
    <line ref={lineRef as any}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial
        color={bolt.color}
        transparent
        opacity={bolt.opacity}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        linewidth={1}
      />
    </line>
  );
}

// ============================================================================
// Data Stream Pulse - Flows through connected nodes like data packets
// ============================================================================

// Create a circular dot texture for round particles
const createDotTexture = (): THREE.Texture => {
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 32;
  const ctx = canvas.getContext('2d')!;
  
  // Draw a soft circular gradient
  const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
  gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
  gradient.addColorStop(0.3, 'rgba(255, 255, 255, 0.8)');
  gradient.addColorStop(0.7, 'rgba(255, 255, 255, 0.3)');
  gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
  
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 32, 32);
  
  const texture = new THREE.CanvasTexture(canvas);
  return texture;
};

// Shared dot texture for all pulses
const dotTexture = createDotTexture();

interface DataPulse {
  id: number;
  nodeIds: string[];  // Path of node IDs
  startTime: number;
  duration: number;   // Total duration for the pulse to traverse all nodes
  color: THREE.Color;
}

function DataStreamPulse({ nodePositions, graphData, pulseSpeed = 1 }: { 
  nodePositions: Map<string, [number, number, number]>;
  graphData: GraphData | null;
  pulseSpeed?: number;
}) {
  const [pulses, setPulses] = useState<DataPulse[]>([]);
  const pulseIdRef = useRef(0);
  
  // Build adjacency list for finding connected paths
  const adjacency = useMemo(() => {
    if (!graphData) return new Map<string, string[]>();
    const adj = new Map<string, string[]>();
    
    for (const link of graphData.links) {
      if (!adj.has(link.concept_a)) adj.set(link.concept_a, []);
      if (!adj.has(link.concept_b)) adj.set(link.concept_b, []);
      adj.get(link.concept_a)!.push(link.concept_b);
      adj.get(link.concept_b)!.push(link.concept_a);
    }
    
    return adj;
  }, [graphData]);
  
  // Get distance from center for a node
  const getDistanceFromCenter = useCallback((nodeId: string): number => {
    const pos = nodePositions.get(nodeId);
    if (!pos) return Infinity;
    return Math.sqrt(pos[0] * pos[0] + pos[1] * pos[1] + pos[2] * pos[2]);
  }, [nodePositions]);
  
  // Find a spiral path - either outward from center or inward from edge
  const findSpiralPath = useCallback((targetLength: number, outward: boolean): string[] => {
    const nodeIds = Array.from(nodePositions.keys());
    if (nodeIds.length < 2) return [];
    
    // Sort nodes by distance from center
    const sortedByDist = [...nodeIds].sort((a, b) => 
      getDistanceFromCenter(a) - getDistanceFromCenter(b)
    );
    
    // Pick starting node - center for outward, edge for inward
    let startCandidates: string[];
    if (outward) {
      // Start from inner 20% of nodes
      startCandidates = sortedByDist.slice(0, Math.max(3, Math.floor(nodeIds.length * 0.2)));
    } else {
      // Start from outer 30% of nodes  
      startCandidates = sortedByDist.slice(Math.floor(nodeIds.length * 0.7));
    }
    
    // Fallback if candidates empty
    if (startCandidates.length === 0) {
      startCandidates = sortedByDist;
    }
    if (startCandidates.length === 0) return [];
    
    // Pick random from candidates
    const startNode = startCandidates[Math.floor(Math.random() * startCandidates.length)];
    const path: string[] = [startNode];
    const visited = new Set<string>([startNode]);
    
    // Walk through nodes, preferring to move outward/inward with slight spiral
    while (path.length < targetLength) {
      const current = path[path.length - 1];
      const currentDist = getDistanceFromCenter(current);
      const currentPos = nodePositions.get(current);
      
      const neighbors = adjacency.get(current) || [];
      const unvisited = neighbors.filter(n => !visited.has(n) && nodePositions.has(n));
      
      let candidates: string[];
      
      if (unvisited.length === 0) {
        // Dead end - find unvisited nodes in the right direction
        candidates = nodeIds.filter(n => !visited.has(n));
        if (candidates.length === 0) break;
      } else {
        candidates = unvisited;
      }
      
      // Score candidates by how well they fit the spiral direction
      const scored = candidates.map(n => {
        const dist = getDistanceFromCenter(n);
        const pos = nodePositions.get(n);
        
        // Direction score: prefer moving outward/inward
        const directionScore = outward 
          ? (dist > currentDist ? 1 : 0.3)
          : (dist < currentDist ? 1 : 0.3);
        
        // Angle score: prefer slight rotation (spiral feel)
        let angleScore = 1;
        if (currentPos && pos) {
          const currentAngle = Math.atan2(currentPos[1], currentPos[0]);
          const nextAngle = Math.atan2(pos[1], pos[0]);
          let angleDiff = Math.abs(nextAngle - currentAngle);
          if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff;
          // Prefer 30-90 degree turns for spiral feel
          angleScore = angleDiff > 0.5 && angleDiff < 1.5 ? 1.5 : 1;
        }
        
        // Add randomness
        const randomScore = 0.5 + Math.random();
        
        return { node: n, score: directionScore * angleScore * randomScore };
      });
      
      // Sort by score and pick from top candidates with some randomness
      scored.sort((a, b) => b.score - a.score);
      const topCount = Math.min(3, scored.length);
      const next = scored[Math.floor(Math.random() * topCount)].node;
      
      path.push(next);
      visited.add(next);
    }
    
    return path;
  }, [nodePositions, adjacency, getDistanceFromCenter]);
  
  // Spawn new pulses
  useEffect(() => {
    const totalNodes = nodePositions.size;
    if (totalNodes < 3) return;
    
    const spawnPulse = () => {
      // Target ~40% of nodes, minimum 5, maximum 50
      const pathLength = Math.max(5, Math.min(50, Math.floor(totalNodes * 0.4)));
      
      // Randomly choose outward or inward spiral
      const outward = Math.random() < 0.5;
      const path = findSpiralPath(pathLength, outward);
      
      if (path.length < 2) return;
      
      const newPulse: DataPulse = {
        id: pulseIdRef.current++,
        nodeIds: path,
        startTime: Date.now(),
        duration: path.length * (250 / pulseSpeed), // Adjust by speed
        color: new THREE.Color().setHSL(
          0.5 + Math.random() * 0.3, // Cyan to purple to pink
          0.6 + Math.random() * 0.3,
          0.5 + Math.random() * 0.3
        ),
      };
      
      setPulses(prev => [...prev, newPulse]);
    };
    
    // Spawn pulses much more frequently - every 200-600ms
    const scheduleNext = () => {
      const delay = 200 + Math.random() * 400;
      return setTimeout(() => {
        spawnPulse();
        scheduleNext();
      }, delay);
    };
    
    // Initial bursts
    for (let i = 0; i < 5; i++) {
      setTimeout(spawnPulse, i * 100);
    }
    const timeout = scheduleNext();
    return () => clearTimeout(timeout);
  }, [nodePositions, findSpiralPath, pulseSpeed]);
  
  // Clean up expired pulses
  useFrame(() => {
    const now = Date.now();
    setPulses(prev => prev.filter(pulse => now - pulse.startTime < pulse.duration + 500));
  });
  
  return (
    <group>
      {pulses.map(pulse => (
        <DataPulseMesh 
          key={pulse.id} 
          pulse={pulse} 
          nodePositions={nodePositions}
        />
      ))}
    </group>
  );
}

function DataPulseMesh({ pulse, nodePositions }: { 
  pulse: DataPulse; 
  nodePositions: Map<string, [number, number, number]>;
}) {
  const trailRef = useRef<THREE.Points>(null);
  const headRef = useRef<THREE.Points>(null);
  
  // Get positions for all nodes in path
  const pathPositions = useMemo(() => {
    return pulse.nodeIds
      .map(id => nodePositions.get(id))
      .filter((p): p is [number, number, number] => p !== undefined)
      .map(p => new THREE.Vector3(...p));
  }, [pulse.nodeIds, nodePositions]);
  
  // Create smooth curve through all points
  const curve = useMemo(() => {
    if (pathPositions.length < 2) return null;
    return new THREE.CatmullRomCurve3(pathPositions, false, 'centripetal', 0.5);
  }, [pathPositions]);
  
  // Animate the pulse traveling along the path
  useFrame(() => {
    if (!trailRef.current || !curve) return;
    
    const elapsed = Date.now() - pulse.startTime;
    const progress = Math.min(elapsed / pulse.duration, 1);
    
    // The "head" of the pulse
    const headT = progress;
    // The "tail" trails behind
    const tailT = Math.max(0, progress - 0.2);
    
    // Create scattered dots along the trail (not continuous)
    const numDots = 12; // Sparse dots
    const positions: number[] = [];
    const sizes: number[] = [];
    
    for (let i = 0; i < numDots; i++) {
      // Irregular spacing - some clustered, some spread
      const baseT = i / numDots;
      const jitter = (Math.sin(i * 7.3) * 0.5 + 0.5) * 0.15; // Pseudo-random jitter
      const t = tailT + (headT - tailT) * (baseT + jitter * (1 - baseT));
      
      if (t >= 0 && t <= 1) {
        const point = curve.getPoint(t);
        positions.push(point.x, point.y, point.z);
        
        // Size varies - smaller toward tail, bigger toward head
        const sizeT = (t - tailT) / (headT - tailT + 0.001);
        sizes.push(0.02 + sizeT * 0.04); // 0.02 to 0.06
      }
    }
    
    if (positions.length > 0) {
      const geometry = trailRef.current.geometry;
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1));
      geometry.attributes.position.needsUpdate = true;
      
      // Fade based on progress
      const material = trailRef.current.material as THREE.PointsMaterial;
      material.opacity = progress < 0.9 ? 0.7 : (1 - progress) * 7;
    }
    
    // Update head position
    if (headRef.current && progress < 1) {
      const headPos = curve.getPoint(headT);
      const headGeom = headRef.current.geometry;
      headGeom.setAttribute('position', new THREE.Float32BufferAttribute([headPos.x, headPos.y, headPos.z], 3));
      headGeom.attributes.position.needsUpdate = true;
      
      // Pulse the head
      const headMaterial = headRef.current.material as THREE.PointsMaterial;
      headMaterial.opacity = 0.8 + Math.sin(elapsed * 0.03) * 0.2;
    }
  });
  
  if (!curve || pathPositions.length < 2) return null;
  
  return (
    <group>
      {/* Trail dots - scattered */}
      <points ref={trailRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array(36), 3]} // 12 dots * 3
          />
        </bufferGeometry>
        <pointsMaterial
          color={pulse.color}
          size={0.08}
          map={dotTexture}
          transparent
          opacity={0.7}
          blending={THREE.AdditiveBlending}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
      
      {/* Head dot - slightly bigger */}
      <points ref={headRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[new Float32Array([0, 0, 0]), 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          color={pulse.color}
          size={0.14}
          map={dotTexture}
          transparent
          opacity={0.9}
          blending={THREE.AdditiveBlending}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
    </group>
  );
}

// ============================================================================
// Main Scene
// ============================================================================

interface SceneProps {
  graphData: GraphData | null;
  activatedConcepts: Map<string, number>;
  onNodeClick?: (nodeId: string) => void;
  pulseSpeed?: number;
}

// Rotating container for the whole graph
function RotatingGroup({ children, speed = 0.05 }: { children: React.ReactNode; speed?: number }) {
  const groupRef = useRef<THREE.Group>(null);
  
  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += speed * delta;
    }
  });
  
  return <group ref={groupRef}>{children}</group>;
}

function Scene({ graphData, activatedConcepts, onNodeClick, pulseSpeed = 1 }: SceneProps) {
  // Calculate 3D positions for nodes - with identity at origin (0,0,0,0)
  const nodeLayout = useMemo(() => {
    if (!graphData) return { positions: new Map<string, [number, number, number]>(), originId: null as string | null };
    
    const positions = new Map<string, [number, number, number]>();
    const nodes = graphData.nodes;
    
    // Find the origin node - the "self" anchor at (0,0,0)
    // Priority: identity > name > most connected node
    const originCandidates = ['identity.name.agent', 'identity.agent', 'name.agent', 'identity', 'name', 'self'];
    let originNode = nodes.find(n => originCandidates.includes(n.id.toLowerCase()));
    
    // Fallback to most connected node if no identity node found
    if (!originNode) {
      originNode = [...nodes].sort((a, b) => b.connections - a.connections)[0];
    }
    
    // Place origin at (0,0,0)
    if (originNode) {
      positions.set(originNode.id, [0, 0, 0]);
    }
    
    // Build adjacency for distance calculation
    const adjacency = new Map<string, Set<string>>();
    for (const link of graphData.links) {
      if (!adjacency.has(link.concept_a)) adjacency.set(link.concept_a, new Set());
      if (!adjacency.has(link.concept_b)) adjacency.set(link.concept_b, new Set());
      adjacency.get(link.concept_a)!.add(link.concept_b);
      adjacency.get(link.concept_b)!.add(link.concept_a);
    }
    
    // Calculate graph distance from origin (BFS)
    const distances = new Map<string, number>();
    if (originNode) {
      distances.set(originNode.id, 0);
      const queue = [originNode.id];
      while (queue.length > 0) {
        const current = queue.shift()!;
        const currentDist = distances.get(current)!;
        const neighbors = adjacency.get(current) || new Set();
        for (const neighbor of neighbors) {
          if (!distances.has(neighbor)) {
            distances.set(neighbor, currentDist + 1);
            queue.push(neighbor);
          }
        }
      }
    }
    
    // Position nodes based on distance from origin
    // Closer to identity = closer to center, shape emerges from topology
    const maxDist = Math.max(...distances.values(), 1);
    const otherNodes = nodes.filter(n => n.id !== originNode?.id);
    
    otherNodes.forEach((node, i) => {
      // Distance from identity determines radius
      const graphDist = distances.get(node.id) ?? maxDist;
      const normalizedDist = graphDist / maxDist;
      
      // Radius: close to identity = near center, far = near edge
      // But contained within sphere (max ~5)
      const radius = 0.5 + normalizedDist * 4.5;
      
      // Angular position from golden ratio for even distribution
      const phi = Math.acos(1 - 2 * (i + 0.5) / otherNodes.length);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      
      // Add slight variation based on connections (more connected = slight pull inward)
      const connectionPull = Math.log10(node.connections + 1) / Math.log10(100) * 0.3;
      const finalRadius = Math.max(0.2, radius - connectionPull);
      
      const x = finalRadius * Math.sin(phi) * Math.cos(theta);
      const y = finalRadius * Math.sin(phi) * Math.sin(theta);
      const z = finalRadius * Math.cos(phi);
      
      positions.set(node.id, [x, y, z]);
    });
    
    return { positions, originId: originNode?.id || null };
  }, [graphData]);
  
  const nodePositions = nodeLayout.positions;
  const originNodeId = nodeLayout.originId;
  
  // Build connections map for gas density
  const nodeConnections = useMemo(() => {
    if (!graphData) return new Map<string, number>();
    const connections = new Map<string, number>();
    graphData.nodes.forEach(node => {
      connections.set(node.id, node.connections);
    });
    return connections;
  }, [graphData]);
  
  // Compute temporal age for each node based on links
  // 0 = oldest (temporal origin), 1 = newest
  const nodeAges = useMemo(() => {
    if (!graphData) return new Map<string, number>();
    
    const ages = new Map<string, number>();
    const timestamps = new Map<string, number>();
    
    // Extract earliest timestamp for each node from its links
    for (const link of graphData.links) {
      if (link.last_fired) {
        const ts = new Date(link.last_fired).getTime();
        
        // Track earliest appearance of each concept
        for (const concept of [link.concept_a, link.concept_b]) {
          const existing = timestamps.get(concept);
          if (!existing || ts < existing) {
            timestamps.set(concept, ts);
          }
        }
      }
    }
    
    if (timestamps.size === 0) return ages;
    
    // Normalize to 0-1 range
    const allTimes = [...timestamps.values()];
    const minTime = Math.min(...allTimes);
    const maxTime = Math.max(...allTimes);
    const range = maxTime - minTime || 1;
    
    timestamps.forEach((ts, concept) => {
      ages.set(concept, (ts - minTime) / range);
    });
    
    return ages;
  }, [graphData]);
  
  if (!graphData) {
    return (
      <>
        <NebulaShell />
        <Text position={[0, 0, 0]} fontSize={0.2} color="#aa88cc">
          Loading...
        </Text>
      </>
    );
  }
  
  return (
    <RotatingGroup speed={0.03}>
      {/* Nebula containment shell with density-aware gas */}
      <NebulaShell nodePositions={nodePositions} nodeConnections={nodeConnections} />
      
      {/* Concept nodes */}
      {graphData.nodes.map((node) => {
        const pos = nodePositions.get(node.id);
        if (!pos) return null;
        
        const activation = activatedConcepts.get(node.id) || 0;
        const isActivated = activation > 0;
        const isOrigin = node.id === originNodeId;
        const age = nodeAges.get(node.id) ?? 0.5;
        
        return (
          <ConceptNodeMesh
            key={node.id}
            position={pos}
            node={node}
            isActivated={isActivated}
            activationLevel={activation}
            onClick={() => onNodeClick?.(node.id)}
            showLabel={node.connections > 5 || isOrigin}
            isOrigin={isOrigin}
            age={age}
          />
        );
      })}
      
      {/* Energy arcs between nodes */}
      {graphData.links.slice(0, 150).map((link, i) => {
        const startPos = nodePositions.get(link.concept_a);
        const endPos = nodePositions.get(link.concept_b);
        if (!startPos || !endPos) return null;
        
        const aActivation = activatedConcepts.get(link.concept_a) || 0;
        const bActivation = activatedConcepts.get(link.concept_b) || 0;
        const isActive = aActivation > 0.1 || bActivation > 0.1;
        
        // Only show strong links or active ones
        if (link.strength < 0.2 && !isActive) return null;
        
        return (
          <EnergyArc
            key={`${link.concept_a}-${link.concept_b}-${i}`}
            start={startPos}
            end={endPos}
            strength={link.strength}
            isActive={isActive}
          />
        );
      })}
      
      {/* Resonance points - where strings intersect in space */}
      <ResonancePoints links={graphData.links} nodePositions={nodePositions} />
      
      {/* Data stream pulses flowing through nodes */}
      <DataStreamPulse nodePositions={nodePositions} graphData={graphData} pulseSpeed={pulseSpeed} />
      
      {/* Storm lightning around the nebula edges */}
      <StormLightning radius={5} />
      
      {/* Lighting */}
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 0, 0]} intensity={1} color="#cc88ff" distance={10} />
      <pointLight position={[5, 5, 5]} intensity={0.5} color="#ffffff" />
      <pointLight position={[-5, -5, 5]} intensity={0.3} color="#8844cc" />
    </RotatingGroup>
  );
}

// ============================================================================
// Structural Scene — orbital solar-system layout
// ============================================================================

const GOLDEN_ANGLE = 2.399963; // ~137.5° — Fibonacci optimal spread

interface StructuralSceneProps {
  data: StructuralGraphData;
  onNodeClick?: (nodeId: string) => void;
}

// ── Orbital ring (orbit path indicator) ──

function OrbitRing({ radius, color, inclination = 0, ascendingNode = 0 }: {
  radius: number; color: string; inclination?: number; ascendingNode?: number;
}) {
  const points = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    const segs = 96;
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius));
    }
    return pts;
  }, [radius]);

  const lineObj = useMemo(() => {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.12,
    });
    return new THREE.Line(geometry, material);
  }, [points, color]);

  return (
    <group rotation={[inclination, ascendingNode, 0]}>
      <primitive object={lineObj} />
    </group>
  );
}

// ── Self node — the glowing sun at the center ──

function SelfNode({ label, onClick }: { label: string; onClick?: () => void }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const coronaRef = useRef<THREE.Mesh>(null);
  const outerRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (coronaRef.current) {
      const pulse = 1 + Math.sin(t * 1.5) * 0.15;
      coronaRef.current.scale.setScalar(pulse);
      (coronaRef.current.material as THREE.MeshBasicMaterial).opacity =
        0.18 + Math.sin(t * 2.3) * 0.06;
    }
    if (outerRef.current) {
      const pulse2 = 1 + Math.sin(t * 0.8) * 0.1;
      outerRef.current.scale.setScalar(pulse2);
    }
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.002;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Core */}
      <mesh ref={meshRef}
        onClick={onClick}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[0.35, 48, 48]} />
        <meshStandardMaterial
          color="#fff8ee"
          emissive="#ffcc66"
          emissiveIntensity={1.5}
          metalness={0.2}
          roughness={0.1}
        />
      </mesh>
      {/* Corona glow */}
      <mesh ref={coronaRef}>
        <sphereGeometry args={[0.7, 32, 32]} />
        <meshBasicMaterial
          color="#ffaa33"
          transparent
          opacity={0.2}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {/* Outer haze */}
      <mesh ref={outerRef}>
        <sphereGeometry args={[1.2, 24, 24]} />
        <meshBasicMaterial
          color="#ff8800"
          transparent
          opacity={0.06}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {/* Point light (the sun illuminates the system) */}
      <pointLight color="#ffcc88" intensity={2.5} distance={25} decay={1.5} />
      <pointLight color="#ff9944" intensity={1} distance={10} decay={2} />
      {/* Label */}
      <Text
        position={[0, 0.6, 0]}
        fontSize={hovered ? 0.22 : 0.18}
        color="#ffddaa"
        anchorX="center"
        anchorY="bottom"
        outlineWidth={0.006}
        outlineColor="#000000"
        fontWeight={700}
      >
        {label}
      </Text>
    </group>
  );
}

// ── Thread planet — orbits the self sun ──

function OrbitalBody({
  node,
  orbitRadius,
  orbitSpeed,
  orbitOffset,
  inclination,
  ascendingNode,
  childCount,
  children,
  onClick,
}: {
  node: StructuralNode;
  orbitRadius: number;
  orbitSpeed: number;
  orbitOffset: number;
  inclination: number;
  ascendingNode: number;
  childCount: number;
  children?: React.ReactNode;
  onClick?: () => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const hsl = THREAD_HSL[node.thread] || [0.76, 0.5, 0.5];
  const threadColor = THREAD_COLORS[node.thread] || '#cc88ff';

  // Size: thread hubs are planets, groups are moons, leaves are dust
  const baseSize = node.depth === 0
    ? 0.15 + Math.min(childCount, 80) * 0.002  // more children = bigger planet
    : node.depth === 1
      ? 0.06 + Math.min(childCount, 30) * 0.001
      : 0.02;
  const size = hovered ? baseSize * 1.5 : baseSize;

  const nodeColor = useMemo(() => {
    const lBoost = node.depth === 0 ? 0.15 : node.depth === 1 ? 0.05 : -0.05;
    return new THREE.Color().setHSL(hsl[0], hsl[1], Math.min(1, hsl[2] + lBoost));
  }, [hsl, node.depth]);

  const glowColor = useMemo(() =>
    new THREE.Color().setHSL(hsl[0], hsl[1] * 0.8, hsl[2] * 0.7),
  [hsl]);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    // Orbital motion — true 3D orbital plane
    const angle = orbitOffset + t * orbitSpeed;
    const fx = Math.cos(angle) * orbitRadius;
    const fz = Math.sin(angle) * orbitRadius;
    // Rotate by inclination (x-axis) then ascending node (y-axis)
    const ci = Math.cos(inclination), si = Math.sin(inclination);
    const ca = Math.cos(ascendingNode), sa = Math.sin(ascendingNode);
    groupRef.current.position.x = fx * ca + fz * ci * sa;
    groupRef.current.position.y = -fz * si;
    groupRef.current.position.z = -fx * sa + fz * ci * ca;

    // Gentle spin
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.008;
    }
    // Glow pulse
    if (glowRef.current) {
      const pulse = 1 + Math.sin(t * 1.8 + orbitOffset) * 0.15;
      glowRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <group ref={groupRef}>
      {/* Planet/moon body */}
      <mesh ref={meshRef}
        onClick={onClick}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[size, node.depth === 0 ? 32 : 16, node.depth === 0 ? 32 : 16]} />
        <meshStandardMaterial
          color={nodeColor}
          emissive={nodeColor}
          emissiveIntensity={node.depth === 0 ? 0.6 : 0.25}
          metalness={0.4}
          roughness={0.35}
        />
      </mesh>
      {/* Glow */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[size * (node.depth === 0 ? 2.2 : 1.8), 16, 16]} />
        <meshBasicMaterial
          color={glowColor}
          transparent
          opacity={node.depth === 0 ? 0.2 : 0.08}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {/* Thread-colored point light for planets */}
      {node.depth === 0 && (
        <pointLight color={threadColor} intensity={0.5} distance={3} decay={2} />
      )}
      {/* Label */}
      {(node.depth <= 1 || hovered) && (
        <Text
          position={[0, size + 0.1, 0]}
          fontSize={node.depth === 0 ? 0.13 : 0.06}
          color={hovered ? '#ffffff' : threadColor}
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.004}
          outlineColor="#000000"
          fontWeight={node.depth === 0 ? 700 : undefined}
        >
          {node.label.length > 24 ? node.label.slice(0, 24) + '…' : node.label}
        </Text>
      )}
      {/* Sub-orbital children are nested inside so they orbit relative to this body */}
      {children}
    </group>
  );
}

// ── Particle trail ring around planets ──

function ParticleTrail({ radius, color, count = 60 }: { radius: number; color: string; count?: number }) {
  const pointsRef = useRef<THREE.Points>(null);

  const { positions, velocities } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const vel = new Float32Array(count); // angular velocity variation
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const r = radius + (Math.random() - 0.5) * 0.1;
      pos[i * 3] = Math.cos(angle) * r;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 0.06;
      pos[i * 3 + 2] = Math.sin(angle) * r;
      vel[i] = 0.5 + Math.random() * 0.5;
    }
    return { positions: pos, velocities: vel };
  }, [radius, count]);

  useFrame((state) => {
    if (!pointsRef.current) return;
    const geo = pointsRef.current.geometry;
    const posAttr = geo.getAttribute('position') as THREE.BufferAttribute;
    const t = state.clock.elapsedTime;
    for (let i = 0; i < count; i++) {
      const baseAngle = (i / count) * Math.PI * 2;
      const angle = baseAngle + t * velocities[i] * 0.3;
      const r = radius + Math.sin(t * 2 + i) * 0.04;
      posAttr.setXYZ(
        i,
        Math.cos(angle) * r,
        Math.sin(t * 1.5 + i * 0.5) * 0.04,
        Math.sin(angle) * r,
      );
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.015}
        color={color}
        transparent
        opacity={0.5}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  );
}

// ── Gravitational lensing — subtle light distortion near Self ──

function GravitationalLensFlare() {
  const ringsRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!ringsRef.current) return;
    const t = state.clock.elapsedTime;
    ringsRef.current.rotation.x = Math.sin(t * 0.3) * 0.2;
    ringsRef.current.rotation.z = Math.cos(t * 0.4) * 0.15;
    ringsRef.current.children.forEach((child, i) => {
      const mesh = child as THREE.Mesh;
      if (mesh.material) {
        (mesh.material as THREE.MeshBasicMaterial).opacity =
          0.03 + Math.sin(t * 1.5 + i * 1.2) * 0.02;
      }
    });
  });

  return (
    <group ref={ringsRef}>
      {[0.7, 1.0, 1.3].map((r, i) => (
        <mesh key={i} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[r - 0.03, r + 0.03, 64]} />
          <meshBasicMaterial
            color="#ffcc66"
            transparent
            opacity={0.04}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}
    </group>
  );
}

// ── Main StructuralScene — the solar system ──

function StructuralScene({ data, onNodeClick }: StructuralSceneProps) {
  // Build parent→children map
  const childMap = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const edge of data.structural) {
      const list = map.get(edge.source) || [];
      list.push(edge.target);
      map.set(edge.source, list);
    }
    return map;
  }, [data]);

  // Build node lookup
  const nodeMap = useMemo(() => {
    const map = new Map<string, StructuralNode>();
    for (const n of data.nodes) map.set(n.id, n);
    return map;
  }, [data]);

  // Count descendants for gravitational mass
  const descendantCount = useMemo(() => {
    const counts = new Map<string, number>();
    const count = (id: string): number => {
      if (counts.has(id)) return counts.get(id)!;
      const kids = childMap.get(id) || [];
      let total = kids.length;
      for (const kid of kids) total += count(kid);
      counts.set(id, total);
      return total;
    };
    for (const n of data.nodes) count(n.id);
    return counts;
  }, [data, childMap]);

  // Self node
  const selfNode = nodeMap.get('self');
  const threads = data.stats.threads;

  // Orbital parameters: mass-sorted (heaviest = innermost), true 3D planes
  const threadOrbits = useMemo(() => {
    const ranked = threads
      .map(tid => ({ tid, mass: descendantCount.get(tid) || 1 }))
      .sort((a, b) => b.mass - a.mass);
    const n = ranked.length;
    return ranked.map((item, rank) => {
      const normRank = n > 1 ? rank / (n - 1) : 0;
      // Orbit radius: heaviest innermost, sqrt spacing for visual balance
      const orbitRadius = 1.8 + Math.sqrt(normRank) * 3.2;
      // Kepler speed: inversely proportional to sqrt(radius)
      const baseSpeed = 0.1 / Math.sqrt(orbitRadius / 2.5);
      const massBoost = 1 + Math.log10(item.mass + 1) * 0.15;
      // Inclination: heavier ≈ ecliptic, lighter = more tilted (up to ~50°)
      const inclination = 0.15 + normRank * 0.75;
      // Ascending node: golden angle for maximum 3D separation
      const ascendingNode = rank * GOLDEN_ANGLE;
      return {
        threadId: item.tid,
        orbitRadius,
        orbitSpeed: baseSpeed * massBoost,
        orbitOffset: rank * GOLDEN_ANGLE * 0.7,
        inclination,
        ascendingNode,
        mass: item.mass,
      };
    });
  }, [threads, descendantCount]);

  return (
    <>
      {/* Ambient light */}
      <ambientLight intensity={0.15} />

      {/* Sun: Self */}
      <SelfNode
        label={selfNode?.label || 'Self'}
        onClick={() => onNodeClick?.('self')}
      />
      <GravitationalLensFlare />

      {/* Orbit rings for each thread — 3D inclined planes */}
      {threadOrbits.map(o => (
        <OrbitRing
          key={`ring-${o.threadId}`}
          radius={o.orbitRadius}
          color={THREAD_COLORS[o.threadId] || '#cc88ff'}
          inclination={o.inclination}
          ascendingNode={o.ascendingNode}
        />
      ))}

      {/* Thread planets and their sub-systems */}
      {threadOrbits.map(o => {
        const threadNode = nodeMap.get(o.threadId);
        if (!threadNode) return null;

        // Depth-1 children sorted by mass (heaviest = innermost moon)
        const d1Kids = (childMap.get(o.threadId) || [])
          .filter(id => nodeMap.get(id)?.depth === 1)
          .map(id => ({ id, mass: descendantCount.get(id) || 1 }))
          .sort((a, b) => b.mass - a.mass);
        const moonCount = d1Kids.length;

        return (
          <OrbitalBody
            key={o.threadId}
            node={threadNode}
            orbitRadius={o.orbitRadius}
            orbitSpeed={o.orbitSpeed}
            orbitOffset={o.orbitOffset}
            inclination={o.inclination}
            ascendingNode={o.ascendingNode}
            childCount={o.mass}
            onClick={() => onNodeClick?.(o.threadId)}
          >
            {/* Particle trail ring around the planet */}
            <ParticleTrail
              radius={0.2 + Math.min(o.mass, 60) * 0.003}
              color={THREAD_COLORS[o.threadId] || '#cc88ff'}
              count={30 + Math.min(o.mass, 60)}
            />

            {/* Orbit rings for moons — 3D inclined planes */}
            {d1Kids.map(({ id: kidId }, j) => {
              const normJ = moonCount > 1 ? j / (moonCount - 1) : 0;
              const moonRadius = 0.3 + normJ * 0.5;
              const moonInc = 0.3 + j * 0.45;
              const moonAsc = j * GOLDEN_ANGLE;
              return (
                <OrbitRing
                  key={`mring-${kidId}`}
                  radius={moonRadius}
                  color={THREAD_COLORS[o.threadId] || '#888'}
                  inclination={moonInc}
                  ascendingNode={moonAsc}
                />
              );
            })}

            {/* Depth-1 moons — mass-sorted, 3D orbital planes */}
            {d1Kids.map(({ id: kidId, mass: kidMass }, j) => {
              const kidNode = nodeMap.get(kidId);
              if (!kidNode) return null;
              const normJ = moonCount > 1 ? j / (moonCount - 1) : 0;
              const moonRadius = 0.3 + normJ * 0.5;
              const moonSpeed = 0.3 / Math.sqrt(moonRadius / 0.3) * (1 + Math.log10(kidMass + 1) * 0.1);
              const moonInc = 0.3 + j * 0.45;
              const moonAsc = j * GOLDEN_ANGLE;

              // Depth-2 leaves orbit this moon
              const d2Kids = (childMap.get(kidId) || []).filter(id =>
                nodeMap.get(id)?.depth === 2
              );
              const leafCount = d2Kids.length;

              return (
                <OrbitalBody
                  key={kidId}
                  node={kidNode}
                  orbitRadius={moonRadius}
                  orbitSpeed={moonSpeed}
                  orbitOffset={j * GOLDEN_ANGLE * 0.7}
                  inclination={moonInc}
                  ascendingNode={moonAsc}
                  childCount={kidMass}
                  onClick={() => onNodeClick?.(kidId)}
                >
                  {/* Depth-2 leaf dust — Fibonacci sphere distribution */}
                  {d2Kids.slice(0, 40).map((leafId, k) => {
                    const leafNode = nodeMap.get(leafId);
                    if (!leafNode) return null;
                    const dustRadius = 0.07 + k * 0.004;
                    const dustSpeed = 0.6 + (k % 5) * 0.15;
                    // Fibonacci sphere: inclinations spread for full 3D coverage
                    const leafInc = Math.acos(1 - 2 * (k + 0.5) / Math.max(leafCount, 1));
                    const leafAsc = k * GOLDEN_ANGLE;
                    return (
                      <OrbitalBody
                        key={leafId}
                        node={leafNode}
                        orbitRadius={dustRadius}
                        orbitSpeed={dustSpeed}
                        orbitOffset={k * GOLDEN_ANGLE}
                        inclination={leafInc}
                        ascendingNode={leafAsc}
                        childCount={0}
                        onClick={() => onNodeClick?.(leafId)}
                      />
                    );
                  })}
                  {/* Extra glow ring if many leaves */}
                  {d2Kids.length > 10 && (
                    <ParticleTrail
                      radius={0.07 + d2Kids.length * 0.004}
                      color={THREAD_COLORS[o.threadId] || '#888'}
                      count={Math.min(d2Kids.length, 40)}
                    />
                  )}
                </OrbitalBody>
              );
            })}
          </OrbitalBody>
        );
      })}

      {/* Distant star field background */}
      <StarField />
    </>
  );
}

// ── Starfield background ──

function StarField() {
  const count = 800;
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Place stars on a large sphere
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 30 + Math.random() * 20;
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    return pos;
  }, []);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#aabbdd"
        transparent
        opacity={0.6}
        sizeAttenuation
      />
    </points>
  );
}

// ============================================================================
// Co-occurrence View (2D)
// ============================================================================

function CooccurrenceView() {
  const [data, setData] = useState<CooccurrenceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [minCount, setMinCount] = useState(2);

  useEffect(() => {
    setLoading(true);
    fetch(`http://localhost:8000/api/linking_core/cooccurrence?limit=200&min_count=${minCount}`)
      .then(r => r.ok ? r.json() : Promise.reject('Failed'))
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [minCount]);

  if (loading) return <div style={{ color: '#bb99dd', padding: 40, textAlign: 'center' }}>Loading co-occurrence data...</div>;
  if (!data || data.pairs.length === 0) return <div style={{ color: '#8877aa', padding: 40, textAlign: 'center' }}>No co-occurrence data yet. Chat more to build associations.</div>;

  const maxCount = data.stats.max_count || 1;

  return (
    <div style={{
      width: '100%', height: '100%', overflow: 'auto',
      background: 'radial-gradient(ellipse at center, #1a0a2e 0%, #0a0612 100%)',
      padding: 24, boxSizing: 'border-box',
    }}>
      {/* Header + filter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <h3 style={{ color: '#dd99ff', margin: 0, fontSize: 16, fontWeight: 600 }}>
          🔗 Co-occurrence Pairs
        </h3>
        <span style={{ color: '#776699', fontSize: 12 }}>
          {data.stats.returned} of {data.stats.total_pairs} pairs
        </span>
        <label style={{ color: '#8877aa', fontSize: 12, marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          Min count:
          <input type="range" min={1} max={20} value={minCount}
            onChange={e => setMinCount(Number(e.target.value))}
            style={{ width: 80, accentColor: '#aa66ff' }} />
          <span style={{ color: '#bb99dd', minWidth: 16 }}>{minCount}</span>
        </label>
      </div>

      {/* Top concepts bar chart */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ color: '#aa88cc', fontSize: 12, marginBottom: 8, fontWeight: 500 }}>Top Concepts</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {data.top_concepts.slice(0, 20).map(c => {
            const pct = c.total_count / (data.top_concepts[0]?.total_count || 1);
            return (
              <div key={c.concept} style={{
                padding: '4px 10px', borderRadius: 6, fontSize: 11,
                background: `rgba(136, 68, 204, ${0.15 + pct * 0.45})`,
                border: '1px solid rgba(170, 100, 255, 0.3)',
                color: '#ddbbff',
              }}>
                {c.concept} <span style={{ color: '#aa88cc' }}>({c.total_count})</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pair table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(170, 100, 255, 0.3)' }}>
            <th style={thStyle}>Concept A</th>
            <th style={thStyle}>Concept B</th>
            <th style={{ ...thStyle, width: 200 }}>Strength</th>
            <th style={{ ...thStyle, width: 60, textAlign: 'right' }}>Count</th>
            <th style={{ ...thStyle, width: 100, textAlign: 'right' }}>Last Seen</th>
          </tr>
        </thead>
        <tbody>
          {data.pairs.map((p, i) => {
            const pct = p.count / maxCount;
            return (
              <tr key={i} style={{ borderBottom: '1px solid rgba(170, 100, 255, 0.1)' }}>
                <td style={tdStyle}>{p.key_a}</td>
                <td style={tdStyle}>{p.key_b}</td>
                <td style={tdStyle}>
                  <div style={{
                    height: 8, borderRadius: 4, overflow: 'hidden',
                    background: 'rgba(170, 100, 255, 0.15)',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: 4, width: `${pct * 100}%`,
                      background: `linear-gradient(90deg, rgba(136, 68, 204, 0.8), rgba(200, 120, 255, 0.8))`,
                    }} />
                  </div>
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{p.count}</td>
                <td style={{ ...tdStyle, textAlign: 'right', color: '#776699', fontSize: 10 }}>
                  {p.last_seen ? new Date(p.last_seen).toLocaleDateString() : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '8px 10px', color: '#aa88cc', fontWeight: 500,
};
const tdStyle: React.CSSProperties = {
  padding: '6px 10px', color: '#ccbbdd',
};

// ============================================================================
// Main Component
// ============================================================================

export default function ConceptGraph3D({ mode = 'ambient', onNodeClick, activationQuery }: ConceptGraph3DProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [structuralData, setStructuralData] = useState<StructuralGraphData | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('cluster');
  const [activatedConcepts, setActivatedConcepts] = useState<Map<string, number>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState('');
  const [reindexing, setReindexing] = useState(false);
  const [reindexResult, setReindexResult] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string>('');
  const [pulseSpeed, setPulseSpeed] = useState(1);
  const [anchored, setAnchored] = useState(true);
  
  // Fetch cluster graph data (existing concept graph)
  const fetchGraph = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        max_nodes: '200',
        anchored: anchored ? 'true' : 'false',
      });
      const res = await fetch(`http://localhost:8000/api/linking_core/graph?${params}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setGraphData(data);
      setError(null);
    } catch (e) {
      setError('Could not load concept graph');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [anchored]);

  // Fetch structural hierarchy graph
  const fetchStructural = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        cross_links: 'true',
        min_cross_strength: '0.15',
        max_cross_links: '200',
      });
      const res = await fetch(`http://localhost:8000/api/linking_core/graph/structural?${params}`);
      if (!res.ok) throw new Error('Failed to fetch structural graph');
      const data = await res.json();
      setStructuralData(data);
      setError(null);
    } catch (e) {
      setError('Could not load structural graph');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);
  
  // Reindex all profiles into concept graph
  const handleReindex = useCallback(async () => {
    setReindexing(true);
    setReindexResult(null);
    try {
      const res = await fetch('http://localhost:8000/api/linking_core/reindex', {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Reindex failed');
      const data = await res.json();
      setReindexResult(`🌀 ${data.total_links} links`);
      fetchGraph();
    } catch (e) {
      setReindexResult('❌ Failed');
      console.error(e);
    } finally {
      setReindexing(false);
      setTimeout(() => setReindexResult(null), 3000);
    }
  }, [fetchGraph]);
  
  // Spread activation
  const runActivation = useCallback(async (query: string) => {
    if (!query.trim()) {
      setActivatedConcepts(new Map());
      setDebugInfo('');
      return;
    }
    
    try {
      const res = await fetch(`http://localhost:8000/api/linking_core/activate/${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Activation failed');
      const data = await res.json();
      
      // Build activation map
      const newActivations = new Map<string, number>();
      
      // Input concepts get full activation
      for (const concept of data.concepts || []) {
        newActivations.set(concept, 1.0);
      }
      
      // Activated concepts get their activation level
      for (const item of data.activated || []) {
        newActivations.set(item.concept, item.activation);
      }
      
      setActivatedConcepts(newActivations);
      setDebugInfo(`Input: [${(data.concepts || []).join(', ')}] → ${data.count || 0} activated`);
    } catch (e) {
      console.error('Activation failed:', e);
      setDebugInfo('Activation error');
    }
  }, []);
  
  // Load graph on mount / when view mode changes
  useEffect(() => {
    if (viewMode === 'cooccurrence') return; // CooccurrenceView handles its own fetch
    setLoading(true);
    if (viewMode === 'cluster') {
      fetchGraph();
    } else {
      fetchStructural();
    }
  }, [fetchGraph, fetchStructural, viewMode]);
  
  // Run activation when query changes (live mode)
  useEffect(() => {
    if (mode === 'live' && activationQuery) {
      runActivation(activationQuery);
    }
  }, [mode, activationQuery, runActivation]);
  
  // Debounced local query input
  useEffect(() => {
    const timer = setTimeout(() => {
      runActivation(queryInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [queryInput, runActivation]);
  
  const is3D = viewMode === 'cluster' || viewMode === 'structure';

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', position: 'relative' }}>
      {/* ── Sidebar ── */}
      <div style={{
        width: 52, minWidth: 52,
        background: 'rgba(12, 6, 24, 0.95)',
        borderRight: '1px solid rgba(170, 100, 255, 0.2)',
        display: 'flex', flexDirection: 'column',
        paddingTop: 8, alignItems: 'center', gap: 2,
        zIndex: 10,
      }}>
        {VIEWS.map(v => {
          const active = viewMode === v.id;
          return (
            <button
              key={v.id}
              onClick={() => setViewMode(v.id)}
              title={v.label}
              style={{
                width: 40, height: 40, borderRadius: 8, border: 'none',
                background: active
                  ? 'linear-gradient(135deg, rgba(136, 68, 204, 0.6), rgba(100, 40, 180, 0.6))'
                  : 'transparent',
                color: active ? '#fff' : '#665588',
                fontSize: 18, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s',
              }}
            >
              {v.icon}
            </button>
          );
        })}

        {/* Divider */}
        <div style={{ width: 28, height: 1, background: 'rgba(170, 100, 255, 0.2)', margin: '6px 0' }} />

        {/* Stats summary */}
        {graphData && (
          <div style={{ fontSize: 9, color: '#776699', textAlign: 'center', lineHeight: 1.4, padding: '0 4px' }}>
            <div>{graphData.stats.unique_concepts}</div>
            <div style={{ fontSize: 8, color: '#554477' }}>nodes</div>
            <div style={{ marginTop: 4 }}>{graphData.stats.total_links}</div>
            <div style={{ fontSize: 8, color: '#554477' }}>links</div>
          </div>
        )}

        {/* Spacer → reindex at bottom */}
        <div style={{ flex: 1 }} />

        {viewMode === 'cluster' && (
          <button
            onClick={handleReindex}
            disabled={reindexing}
            title={reindexing ? 'Reindexing...' : 'Reindex concept graph'}
            style={{
              width: 36, height: 36, borderRadius: 8, border: 'none',
              background: reindexing ? 'rgba(100,100,100,0.2)' : 'rgba(136, 68, 204, 0.25)',
              color: '#bb99dd', fontSize: 14, cursor: reindexing ? 'wait' : 'pointer',
              marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {reindexing ? '🔄' : '📊'}
          </button>
        )}
        {reindexResult && (
          <div style={{ fontSize: 8, color: reindexResult.includes('🌀') ? '#88cc88' : '#ff6b6b', textAlign: 'center', marginBottom: 6, padding: '0 2px' }}>
            {reindexResult}
          </div>
        )}
      </div>

      {/* ── Main content area ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {viewMode === 'cooccurrence' ? (
          <CooccurrenceView />
        ) : (
          <div
            style={{ width: '100%', height: '100%', background: 'radial-gradient(ellipse at center, #1a0a2e 0%, #0a0612 100%)' }}
            onWheel={(e) => e.preventDefault()}
          >
            {/* 3D Canvas */}
            <Canvas
              camera={{
                position: viewMode === 'structure' ? [5, 6, 9] : [0, 0, 12],
                fov: 50,
              }}
              style={{ width: '100%', height: '100%', touchAction: 'none' }}
              key={viewMode}
            >
              {viewMode === 'cluster' ? (
                <Scene
                  graphData={graphData}
                  activatedConcepts={activatedConcepts}
                  onNodeClick={onNodeClick}
                  pulseSpeed={pulseSpeed}
                />
              ) : structuralData ? (
                <StructuralScene
                  data={structuralData}
                  onNodeClick={onNodeClick}
                />
              ) : null}
              {viewMode === 'structure' ? (
                <OrbitControls
                  enableDamping dampingFactor={0.12}
                  rotateSpeed={0.8} zoomSpeed={1.2} panSpeed={0.8}
                  minDistance={3} maxDistance={40}
                />
              ) : (
                <FlyControls moveSpeed={8} lookSpeed={0.002} />
              )}
            </Canvas>

            {/* Controls hint */}
            <div style={{
              position: 'absolute', top: 12, left: 12,
              fontSize: '0.7rem', color: 'rgba(180, 160, 220, 0.6)', pointerEvents: 'none',
            }}>
              {viewMode === 'cluster'
                ? '↑↓ forward/back • ←→ turn • WASD move • Q/E up/down • Drag look'
                : '🖱️ Drag orbit • Scroll zoom • Right-drag pan'}
            </div>

            {/* Query input — cluster mode only */}
            {viewMode === 'cluster' && (
              <div style={{
                position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
              }}>
                <div style={{
                  display: 'flex', gap: 8, padding: 12,
                  background: 'rgba(20, 10, 40, 0.9)', borderRadius: 12,
                  border: '1px solid rgba(170, 100, 255, 0.3)',
                  boxShadow: '0 0 30px rgba(136, 68, 204, 0.3)',
                }}>
                  <input
                    type="text" value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="Type to activate concepts..."
                    style={{
                      width: 300, padding: '10px 14px',
                      background: 'rgba(0, 0, 0, 0.5)',
                      border: '1px solid rgba(170, 100, 255, 0.4)',
                      borderRadius: 8, color: '#fff', fontSize: 14, outline: 'none',
                    }}
                  />
                  <button
                    onClick={() => { setQueryInput(''); setActivatedConcepts(new Map()); setDebugInfo(''); }}
                    style={{
                      padding: '10px 20px',
                      background: 'linear-gradient(135deg, rgba(136, 68, 204, 0.4), rgba(68, 34, 102, 0.4))',
                      border: '1px solid rgba(170, 100, 255, 0.4)',
                      borderRadius: 8, color: '#fff', cursor: 'pointer', fontWeight: 500,
                    }}
                  >Clear</button>
                </div>
                {debugInfo && (
                  <div style={{ fontSize: 11, color: '#aa88cc', background: 'rgba(0,0,0,0.5)', padding: '4px 12px', borderRadius: 4 }}>
                    {debugInfo}
                  </div>
                )}
              </div>
            )}

            {/* Stats overlay */}
            <div style={{
              position: 'absolute', top: 12, left: 12,
              padding: 12, marginTop: 24,
              background: 'rgba(20, 10, 40, 0.85)', borderRadius: 10,
              border: '1px solid rgba(170, 100, 255, 0.25)',
              color: '#bb99dd', fontSize: 12,
            }}>
              {loading ? (
                <span>Loading...</span>
              ) : error ? (
                <span style={{ color: '#ff6b6b' }}>{error}</span>
              ) : viewMode === 'cluster' && graphData ? (
                <>
                  <div>{graphData.stats.unique_concepts} concepts • {graphData.stats.total_links} links</div>
                  <div>Avg strength: {graphData.stats.avg_strength.toFixed(2)}</div>
                  {activatedConcepts.size > 0 && (
                    <div style={{ color: '#ffcc66', fontWeight: 500, marginTop: 4 }}>
                      ⚡ {activatedConcepts.size} active
                    </div>
                  )}
                </>
              ) : viewMode === 'structure' && structuralData ? (
                <>
                  <div>{structuralData.stats.node_count} nodes • {structuralData.stats.structural_count} edges</div>
                  <div>{structuralData.stats.associative_count} cross-links</div>
                  <div style={{ marginTop: 6, fontSize: 11 }}>
                    {structuralData.stats.threads.map(t => (
                      <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                        <span style={{
                          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                          background: THREAD_COLORS[t] || '#888',
                        }} />
                        <span>{t}</span>
                        <span style={{ color: '#776699', marginLeft: 'auto' }}>
                          {structuralData.nodes.filter(n => n.thread === t).length}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>

            {/* Right panel — controls */}
            {is3D && (
              <div style={{
                position: 'absolute', top: 12, right: 12,
                padding: 10, background: 'rgba(20, 10, 40, 0.75)', borderRadius: 10,
                border: '1px solid rgba(170, 100, 255, 0.2)',
                color: '#8877aa', fontSize: 11, maxWidth: 150,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4, color: '#aa99cc' }}>Controls</div>
                <div>🖱️ Drag to orbit</div>
                <div>⚙️ Scroll to zoom</div>
                {viewMode === 'cluster' && <div>⌨️ Type to activate</div>}
                <div>💡 Click nodes</div>

                {viewMode === 'cluster' && (
                  <>
                    <div style={{ marginTop: 8, borderTop: '1px solid rgba(170, 100, 255, 0.2)', paddingTop: 8 }}>
                      <div style={{ marginBottom: 4 }}>⚡ Pulse: {pulseSpeed.toFixed(1)}x</div>
                      <input type="range" min="0.2" max="3" step="0.1" value={pulseSpeed}
                        onChange={(e) => setPulseSpeed(parseFloat(e.target.value))}
                        style={{ width: '100%', accentColor: '#aa66ff', cursor: 'pointer' }}
                      />
                    </div>
                    <div style={{ marginTop: 8, borderTop: '1px solid rgba(170, 100, 255, 0.2)', paddingTop: 8 }}>
                      <button
                        onClick={() => setAnchored(prev => !prev)}
                        title={anchored ? 'Showing fact-anchored only' : 'Showing all concepts'}
                        style={{
                          width: '100%', padding: '5px 8px', borderRadius: 6, fontSize: 10,
                          background: anchored
                            ? 'linear-gradient(135deg, rgba(68, 204, 136, 0.35), rgba(34, 102, 68, 0.35))'
                            : 'linear-gradient(135deg, rgba(136, 68, 204, 0.25), rgba(68, 34, 102, 0.25))',
                          border: anchored ? '1px solid rgba(100, 220, 150, 0.5)' : '1px solid rgba(170, 100, 255, 0.3)',
                          color: anchored ? '#88ddaa' : '#9977bb',
                          cursor: 'pointer', fontWeight: 500, textAlign: 'left',
                        }}
                      >
                        {anchored ? '🔒 Anchored facts' : '🌐 All concepts'}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
