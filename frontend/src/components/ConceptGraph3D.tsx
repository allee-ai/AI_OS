/**
 * ConceptGraph3D - 3D Neural Nebula Visualization
 * ================================================
 * A contained purple nebula sphere with concept nodes inside.
 * 
 * The purple gas swirls as a bounding "containment field"
 * Silver/gold nodes float inside representing concepts
 * Lightning arcs between nodes show activation spreading
 * 
 * This is the visual representation of Nola's associative memory.
 * "Attention over concepts, not tokens" - made visible.
 */

import { useRef, useState, useEffect, useMemo, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Sphere } from '@react-three/drei';
import * as THREE from 'three';

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
  
  // Outer swirling shell
  const outerParticles = useMemo(() => {
    const count = 4000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    for (let i = 0; i < count; i++) {
      // Spherical shell distribution
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const radius = 3.5 + Math.random() * 0.5; // Shell between 3.5-4.0
      
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);
      
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
  }, []);
  
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
  const baseSize = isOrigin ? 0.2 : 0.04 + logConnections * 0.1;
  const size = hovered ? baseSize * 1.5 : baseSize;
  
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
// Main Scene
// ============================================================================

interface SceneProps {
  graphData: GraphData | null;
  activatedConcepts: Map<string, number>;
  onNodeClick?: (nodeId: string) => void;
}

function Scene({ graphData, activatedConcepts, onNodeClick }: SceneProps) {
  // Calculate 3D positions for nodes - with identity at origin (0,0,0,0)
  const nodeLayout = useMemo(() => {
    if (!graphData) return { positions: new Map<string, [number, number, number]>(), originId: null as string | null };
    
    const positions = new Map<string, [number, number, number]>();
    const nodes = graphData.nodes;
    
    // Find the origin node - the "self" anchor at (0,0,0)
    // Priority: nola > identity > name > most connected node
    const originCandidates = ['nola', 'identity.name.nola', 'identity.nola', 'name.nola', 'identity', 'name', 'self'];
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
      // But contained within sphere (max 2.8)
      const radius = 0.3 + normalizedDist * 2.5;
      
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
    <>
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
      
      {/* Lighting */}
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 0, 0]} intensity={1} color="#cc88ff" distance={10} />
      <pointLight position={[5, 5, 5]} intensity={0.5} color="#ffffff" />
      <pointLight position={[-5, -5, 5]} intensity={0.3} color="#8844cc" />
    </>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ConceptGraph3D({ mode = 'ambient', onNodeClick, activationQuery }: ConceptGraph3DProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [activatedConcepts, setActivatedConcepts] = useState<Map<string, number>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [queryInput, setQueryInput] = useState('');
  const [reindexing, setReindexing] = useState(false);
  const [reindexResult, setReindexResult] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<string>('');
  
  // Fetch graph data
  const fetchGraph = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/linking_core/graph?max_nodes=200');
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
      setReindexResult(`✅ ${data.total_links} links`);
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
      for (const concept of data.input_concepts) {
        newActivations.set(concept, 1.0);
      }
      
      // Activated concepts get their activation level
      for (const item of data.activated) {
        newActivations.set(item.concept, item.activation);
      }
      
      setActivatedConcepts(newActivations);
      setDebugInfo(`Input: [${data.input_concepts.join(', ')}] → ${data.total_activated} activated`);
    } catch (e) {
      console.error('Activation failed:', e);
      setDebugInfo('Activation error');
    }
  }, []);
  
  // Load graph on mount
  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);
  
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
  
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: 'radial-gradient(ellipse at center, #1a0a2e 0%, #0a0612 100%)' }}>
      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [0, 0, 8], fov: 50 }}
        style={{ width: '100%', height: '100%' }}
      >
        <Scene
          graphData={graphData}
          activatedConcepts={activatedConcepts}
          onNodeClick={onNodeClick}
        />
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          autoRotate={mode === 'ambient'}
          autoRotateSpeed={0.3}
          minDistance={4}
          maxDistance={15}
        />
      </Canvas>
      
      {/* Query input overlay */}
      <div style={{
        position: 'absolute',
        bottom: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 8,
      }}>
        <div style={{
          display: 'flex',
          gap: 8,
          padding: 12,
          background: 'rgba(20, 10, 40, 0.9)',
          borderRadius: 12,
          border: '1px solid rgba(170, 100, 255, 0.3)',
          boxShadow: '0 0 30px rgba(136, 68, 204, 0.3)',
        }}>
          <input
            type="text"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            placeholder="Type to activate concepts..."
            style={{
              width: 300,
              padding: '10px 14px',
              background: 'rgba(0, 0, 0, 0.5)',
              border: '1px solid rgba(170, 100, 255, 0.4)',
              borderRadius: 8,
              color: '#fff',
              fontSize: 14,
              outline: 'none',
            }}
          />
          <button
            onClick={() => {
              setQueryInput('');
              setActivatedConcepts(new Map());
              setDebugInfo('');
            }}
            style={{
              padding: '10px 20px',
              background: 'linear-gradient(135deg, rgba(136, 68, 204, 0.4), rgba(68, 34, 102, 0.4))',
              border: '1px solid rgba(170, 100, 255, 0.4)',
              borderRadius: 8,
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Clear
          </button>
        </div>
        {debugInfo && (
          <div style={{ fontSize: 11, color: '#aa88cc', background: 'rgba(0,0,0,0.5)', padding: '4px 12px', borderRadius: 4 }}>
            {debugInfo}
          </div>
        )}
      </div>
      
      {/* Stats overlay */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: 16,
        padding: 14,
        background: 'rgba(20, 10, 40, 0.85)',
        borderRadius: 12,
        border: '1px solid rgba(170, 100, 255, 0.25)',
        color: '#bb99dd',
        fontSize: 12,
        boxShadow: '0 0 20px rgba(136, 68, 204, 0.2)',
      }}>
        {loading ? (
          <span>Loading graph...</span>
        ) : error ? (
          <span style={{ color: '#ff6b6b' }}>{error}</span>
        ) : graphData ? (
          <>
            <div style={{ fontWeight: 600, marginBottom: 6, color: '#dd99ff', fontSize: 14 }}>
              🔮 Linking Core
            </div>
            <div>{graphData.stats.unique_concepts} concepts</div>
            <div>{graphData.stats.total_links} links</div>
            <div>Avg: {graphData.stats.avg_strength.toFixed(2)}</div>
            {activatedConcepts.size > 0 && (
              <div style={{ marginTop: 8, color: '#ffcc66', fontWeight: 500 }}>
                ⚡ {activatedConcepts.size} active
              </div>
            )}
            <button
              onClick={handleReindex}
              disabled={reindexing}
              style={{
                marginTop: 12,
                padding: '8px 14px',
                background: reindexing ? 'rgba(100, 100, 100, 0.3)' : 'linear-gradient(135deg, rgba(136, 68, 204, 0.5), rgba(68, 34, 102, 0.5))',
                border: '1px solid rgba(170, 100, 255, 0.4)',
                borderRadius: 6,
                color: '#fff',
                fontSize: 11,
                cursor: reindexing ? 'wait' : 'pointer',
                width: '100%',
              }}
            >
              {reindexing ? '🔄 Indexing...' : '📊 Reindex'}
            </button>
            {reindexResult && (
              <div style={{ marginTop: 6, fontSize: 10, color: reindexResult.includes('✅') ? '#88cc88' : '#ff6b6b' }}>
                {reindexResult}
              </div>
            )}
          </>
        ) : null}
      </div>
      
      {/* Instructions */}
      <div style={{
        position: 'absolute',
        top: 16,
        right: 16,
        padding: 12,
        background: 'rgba(20, 10, 40, 0.75)',
        borderRadius: 10,
        border: '1px solid rgba(170, 100, 255, 0.2)',
        color: '#8877aa',
        fontSize: 11,
        maxWidth: 160,
      }}>
        <div style={{ fontWeight: 600, marginBottom: 6, color: '#aa99cc' }}>Controls</div>
        <div>🖱️ Drag to orbit</div>
        <div>⚙️ Scroll to zoom</div>
        <div>⌨️ Type to activate</div>
        <div>💡 Click nodes</div>
      </div>
    </div>
  );
}
