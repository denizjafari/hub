import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation as R

# Define segment lengths
L_trunk = 0.5
L_upper = 0.3
L_forearm = 0.25
L_hand = 0.15

# Define helper
def direction(theta):
    return np.array([np.sin(theta), np.cos(theta)])

# === Forward Kinematics === #
def forward_kinematics(theta_T, theta_S, theta_E, theta_W):
    pelvis = np.array([0.0, 0.0])
    shoulder = pelvis + L_trunk * direction(theta_T)
    elbow = shoulder + L_upper * direction(theta_T + theta_S)
    wrist = elbow + L_forearm * direction(theta_T + theta_S + theta_E)
    hand = wrist + L_hand * direction(theta_T + theta_S + theta_E + theta_W)
    return pelvis, shoulder, elbow, wrist, hand

# === Inverse Kinematics (for fixed trunk) === #
def inverse_kinematics(hand_target, theta_T):
    # Compute shoulder position
    pelvis = np.array([0.0, 0.0])
    shoulder = pelvis + L_trunk * direction(theta_T)
    
    # Vector from shoulder to hand
    vec = hand_target - shoulder
    dist = np.linalg.norm(vec)
    
    # Link lengths
    L1 = L_upper
    L2 = L_forearm + L_hand  # assume straight wrist
    
    # Check reachability
    if dist > (L1 + L2):
        raise ValueError("Target unreachable")
    
    # Law of cosines
    cos_angle_E = (L1**2 + L2**2 - dist**2) / (2 * L1 * L2)
    theta_E = np.pi - np.arccos(np.clip(cos_angle_E, -1.0, 1.0))  # Elbow angle
    
    # Shoulder angle
    angle_a = np.arctan2(vec[1], vec[0])
    cos_angle_b = (L1**2 + dist**2 - L2**2) / (2 * L1 * dist)
    angle_b = np.arccos(np.clip(cos_angle_b, -1.0, 1.0))
    theta_S = angle_a - theta_T - angle_b

    # Wrist angle (assume straight for now)
    theta_W = -theta_S - theta_E
    
    return theta_S, theta_E, theta_W

def quaternion_to_matrix(q):
    """Convert quaternion [w, x, y, z] to 3x3 rotation matrix."""
    return R.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()


def forward_kinematics_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, l_trunk, l_upperarm, l_lowerarm):
    """
    Compute hand position in global frame using IMU quaternions for each segment.
    q_*: quaternion [w, x, y, z] for each segment
    l_*: length of each segment (scalars)
    Returns: 3D position of hand in global frame
    """
    # Rotation matrices
    R_trunk = quaternion_to_matrix(q_trunk)
    R_shoulder = quaternion_to_matrix(q_shoulder)
    R_upperarm = quaternion_to_matrix(q_upperarm)
    R_lowerarm = quaternion_to_matrix(q_lowerarm)

    # Homogeneous transforms
    T_trunk = np.eye(4)
    T_trunk[:3, :3] = R_trunk
    T_trunk[:3, 3] = [0, 0, 0]  # Assume trunk base at origin

    T_shoulder = np.eye(4)
    T_shoulder[:3, :3] = R_shoulder
    T_shoulder[:3, 3] = [0, 0, l_trunk]  # Shoulder offset from trunk

    T_upperarm = np.eye(4)
    T_upperarm[:3, :3] = R_upperarm
    T_upperarm[:3, 3] = [0, 0, l_upperarm]  # Elbow offset from shoulder

    T_lowerarm = np.eye(4)
    T_lowerarm[:3, :3] = R_lowerarm
    T_lowerarm[:3, 3] = [0, 0, l_lowerarm]  # Wrist offset from elbow

    # Chain the transforms
    T_hand = T_trunk @ T_shoulder @ T_upperarm @ T_lowerarm
    hand_pos = T_hand[:3, 3]
    return hand_pos

def compute_joint_angles_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, seq="xyz"):
    """
    Compute joint angles (Euler) from IMU quaternions for trunk, shoulder, upper arm, lower arm.
    q_*: quaternion [w, x, y, z] for each segment
    seq: Euler sequence (default 'xyz')
    Returns: dict of joint angles in radians for each joint
    """
    # Convert to scipy Rotation objects
    r_trunk = R.from_quat([q_trunk[1], q_trunk[2], q_trunk[3], q_trunk[0]])
    r_shoulder = R.from_quat([q_shoulder[1], q_shoulder[2], q_shoulder[3], q_shoulder[0]])
    r_upperarm = R.from_quat([q_upperarm[1], q_upperarm[2], q_upperarm[3], q_upperarm[0]])
    r_lowerarm = R.from_quat([q_lowerarm[1], q_lowerarm[2], q_lowerarm[3], q_lowerarm[0]])

    # Relative rotations
    r_shoulder_rel = r_shoulder * r_trunk.inv()
    r_upperarm_rel = r_upperarm * r_shoulder.inv()
    r_lowerarm_rel = r_lowerarm * r_upperarm.inv()

    # Euler angles (joint angles)
    trunk_angles = r_trunk.as_euler(seq)
    shoulder_angles = r_shoulder_rel.as_euler(seq)
    elbow_angles = r_upperarm_rel.as_euler(seq)
    wrist_angles = r_lowerarm_rel.as_euler(seq)

    return {
        'trunk': trunk_angles,
        'shoulder': shoulder_angles,
        'elbow': elbow_angles,
        'wrist': wrist_angles
    }

# === Example usage === #
theta_T = np.radians(10)  # trunk flexion
theta_S = np.radians(45)
theta_E = np.radians(90)
theta_W = np.radians(30)

# Forward Kinematics
pts = forward_kinematics(theta_T, theta_S, theta_E, theta_W)

# Plotting
x = [p[0] for p in pts]
y = [p[1] for p in pts]
plt.plot(x, y, '-o', linewidth=3)
plt.gca().set_aspect('equal')
plt.grid()
plt.title("Forward Kinematics - Trunk and Upper Limb")
plt.xlabel("X (m)")
plt.ylabel("Y (m)")
plt.show()

# Inverse Kinematics
hand_target = pts[-1]  # target is known hand position
theta_S_ik, theta_E_ik, theta_W_ik = inverse_kinematics(hand_target, theta_T)
print("IK solution (degrees): Shoulder =", np.degrees(theta_S_ik),
      "Elbow =", np.degrees(theta_E_ik), "Wrist =", np.degrees(theta_W_ik))

# Example usage for IMU-based FK:
# q_trunk = [1, 0, 0, 0]  # Identity quaternion
# q_shoulder = [1, 0, 0, 0]
# q_upperarm = [1, 0, 0, 0]
# q_lowerarm = [1, 0, 0, 0]
# l_trunk = 0.5
# l_upperarm = 0.3
# l_lowerarm = 0.25
# hand_pos = forward_kinematics_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, l_trunk, l_upperarm, l_lowerarm)
# print("Hand position from IMUs:", hand_pos)

# Example usage for computing joint angles from IMUs:
# q_trunk = [1, 0, 0, 0]
# q_shoulder = [1, 0, 0, 0]
# q_upperarm = [1, 0, 0, 0]
# q_lowerarm = [1, 0, 0, 0]
# angles = compute_joint_angles_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, seq="xyz")
# print("Joint angles (radians):", angles)

if __name__ == "__main__":
    # Example quaternions (identity, no rotation)
    q_trunk = [1, 0, 0, 0]
    q_shoulder = [1, 0, 0, 0]
    q_upperarm = [1, 0, 0, 0]
    q_lowerarm = [1, 0, 0, 0]

    # Example segment lengths (meters)
    l_trunk = 0.5
    l_upperarm = 0.3
    l_lowerarm = 0.25

    # Forward kinematics
    hand_pos = forward_kinematics_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, l_trunk, l_upperarm, l_lowerarm)
    print("Hand position (global frame):", hand_pos)

    # Inverse kinematics (joint angles)
    angles = compute_joint_angles_from_imus(q_trunk, q_shoulder, q_upperarm, q_lowerarm, seq="xyz")
    print("Joint angles (xyz, radians):")
    for joint, ang in angles.items():
        print(f"  {joint}: {ang}")
