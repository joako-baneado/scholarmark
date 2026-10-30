---
title: RESEARCH ARTICLE Lightweight and efficient skeleton-based sports activity recognition
  with ASTM-Net
doi: 10.1371/journal.pone.0324605
year: 2025
source_pdf: Lightweight and efficient skeleton-based sports activity recognition with
  ASTM-Net.pdf
---

![Figure p.1](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p1_1.png)

# RESEARCH ARTICLE Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net

2*, Ying Jia^{3}, Ning Zhang3, GuoJin Zhao4, XiuPing Wang4, Bin Wu^{1}, Mei Xue Chunlei Zhang4

1  College of Light Textile and Chemical Engineering, Binzhou Polytechnic, Shandong, China, 2  School of Information Engineering, Binzhou Polytechnic, Shandong, China, 3  Youth League committee, Binzhou Polytechnic, Shandong, China, 4  Shandong Binzhou Vocational College, Shandong, China

* kutzferraroyam@zohomail.jp

## Abstract

Human Activity Recognition (HAR) plays a pivotal role in video understanding, with applications ranging from surveillance to virtual reality. Skeletal data has emerged as a robust modality for HAR, overcoming challenges such as noisy backgrounds and lighting variations. However, current Graph Convolutional Network (GCNN)–based methods for skeletal activity recognition face two key limitations: (1) they fail to cap­

ture dynamic changes in node affinities induced by movements, and (2) they overlook the interplay between spatial and temporal information critical for recognizing com­ plex actions. To address these challenges, we propose ASTM‐Net, an Activity‐aware SpatioTemporal Multi‐branch graph convolutional network comprising two novel mod­ ules. First, the Activity‐aware Spatial Graph convolution Module (ASGM) dynamically models Activity‐Aware Adjacency Graphs (3A‐Graphs) by fusing a manually initialized physical graph, a learnable graph optimized end‐to‐end, and a dynamically inferred, activity‐related graph—thereby capturing evolving spatial affinities. Second, we intro­

OPEN ACCESS

Citation: Wu B, Xue M, Jia Y, Zhang N, Zhao G, Wang X, et al. (2025) Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net. PLoS One 20(7): e0324605. https:// doi.org/10.1371/journal.pone.0324605

Editor: Guangyin Jin, National University of Defense Technology, CHINA

Received: March 22, 2025

duce the Temporal Multi‐branch Graph convolution Module (TMGM), which employs parallel branches of channel‐reduction, dilated temporal convolutions with varied dila­ tion rates, pooling, and pointwise convolutions to effectively model both fine‐grained and long‐range temporal dependencies. This multi‐branch design not only addresses diverse action speeds and durations but also maintains parameter efficiency. By integrating ASGM and TMGM, ASTM‐Net jointly captures spatial–temporal mutu­ alities with significantly reduced computational cost. Extensive experiments on NTU‐RGB + D, NTU‐RGB + D 120, and Toyota Smarthome demonstrate ASTM‐Net’s superiority: it outperforms DualHead‐Net‐ALLs by 0.31% on NTU‐RGB + D X‐Sub and surpasses SkateFormer by 2.22% on Toyota Smarthome Cross‐Subject; it reduces parameters by 51.9% and FLOPs by 49.7% compared to MST‐GCNN‐ALLs while improving accuracy by 0.82%; and under 30% random node occlusion, it achieves 86.94% accuracy—3.49% higher than CBAM‐STGCN.

Accepted: April 28, 2025

Published: July 8, 2025

Copyright: © 2025 Wu et al. This is an open access article distributed under the terms of the Creative Commons Attribution License, which permits unrestricted use, distribution, and reproduction in any medium, provided the original author and source are credited.

Data availability statement: All three datasets include human subjects whose faces or identifying features may appear (even if blurred in Toyota Smarthome), posing potential privacy or re‐identification risks. Although original releases do not explicitly cite IRB approval, most institutions require local ethics-­ committee (IRB/IEC) review before using any

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 1 / 30 human‐derived imagery or skeletal data. You should therefore secure your own Institutional Review Board (IRB) or Ethics Committee clearance before downloading or processing these datasets. The NTU RGB+D (60‐class) and NTU RGB+D 120 datasets are governed by ROSE Lab’s “academic‐research‐only” license: you must register at (https://rose1. ntu.edu.sg/dataset/actionRecognition/) and agree not to redistribute, derive new datasets from, or use the data for any commercial purpose. All subject images may only be shown in academic publications or presentations, and any infringement (including partial use) automatically terminates your rights under the License. These terms are imposed by the ROSE Lab at Nanyang Technological University (NTU). For access requests or questions, email WangQ@ntu.edu.sg or write to Rapid-Rich Object Search (ROSE) Lab, School of EEE, 50 Nanyang Ave, S2-B4b-13, Singapore 639798. Toyota Smarthome (Trimmed & Untrimmed) data is owned by Toyota Motor Europe NV/SA and released via Inria under a non-­commercial, scientific-research license. You may install and use the data only for free, non-­commercial research or educational purposes; any reproduction, modification, distribution, reverse-engineering or commercial use is strictly prohibited. By filling the request form at (https://project.inria.fr/toyotasmarthome/) you acknowledge and accept these terms. Inria manages data access—direct inquiries or download requests to toyotasmarthome@inria. fr. The full license text is available at (https:// project.inria.fr/toyotasmarthome/files/2020/12/ License_v2.pdf).

## I.  Introduction

Human Activity Recognition (HAR) aims to identify human activities based on the full execution of actions captured in videos, serving as a core task in video understand­ ing [1]. It has already found widespread applications in daily life. For instance, activity recognition algorithms power visual surveillance systems that assist in capturing criminals through video analysis, reducing the risks of criminal activities [2]. Video retrieval enables users to search for videos matching textual descriptions (e.g., titles or keywords) on the internet [3]. Additionally, virtual reality (VR) technologies based on depth sensor data have attracted a large audience across all age groups in the gaming industry [4]. Existing research has explored various modalities for video feature representation, such as RGB frames, optical flow, and skeletal data. Among these, skelecton-based activity recognition has gained increasing attention in recent years due to advances in human pose estimation algorithms [5,6] and the robustness of skelecton data, which captures human activity information without being influenced by noisy backgrounds or variations in lighting [7].

With the development of deep learning, significant progress has been achieved in skelecton-based activity recognition using deep learning methods. Early approaches treated skeletal trajectories as either coordinate vector sequences or grid-like struc­ tures, inputting them into Recurrent Neural Networks (RNNs) [8] or Convolutional Neural Networks (ConvNets) [9]. However, RNNs and ConvNets are inherently designed for regular Euclidean data, and due to the irregular nature of skelecton data, these methods fail to fully exploit the affinities among nodes [8]. Graph Convo­ lutional Neural Networks (GCNNs) [10], which excel in handling irregular data, have thus been introduced for modeling skelecton data.

For skelecton-based activity recognition, we transform skeletal data into a graph representation based on the physical connections between human nodes and encode the affinities among nodes using an adjacency matrix. On this basis, we define the implementation process of spatiotemporal graph convolution over the skelecton graph and skelecton trajectories. Finally, the spatiotemporal graph convolution is employed to extract skeletal features for human activity classification.

Although existing GCNN-based methods have demonstrated notable performance, most approaches alternate spatial graph convolutions and temporal graph convolu­ tions independently [11–14]. This separation introduces two key limitations:

Specifically, the impact of activity on node affinities can be summarized in two aspects:

upper limb during a “wave” activity). Similarly, mutualities between nodes from different body parts (e.g., both hands during a “clap” activity) indicate affinities caused by coordinated movements.

2)	Variation in activity patterns across trajectories: Different skelecton trajectories demonstrate diverse activity patterns (e.g., speed or acceleration). Even when performing the same activity, individuals may exhibit unique activity patterns. Leveraging these rich activity patterns is essential for building more robust models.

Additionally, existing GCNN-based methods suffer from critical limitations in robustness and efficiency. These limitations stem from a fundamental disconnect between spatial graph learning and temporal dynamics, hindering both robustness to real-world variations and computational efficiency (These will be analyzed in detail in the later experimental sections).

To address these limitations, we propose an Activity Aware Spatial Graph Convolution Module (ASGM) to dynamically and efficiently model Activity Aware Adjacency Graph (3A-Graph). Specifically, the 3A-Graph, i.e., G, comprises three components:

1)	A manually initialized graph A based on physical node connections.

2)	A trainable graph B, optimized along with the network.

3)	A dynamically inferred activity-related graph C, capturing the temporal affinity variations among nodes.

To learn G, we first employ an information extraction module to obtain semantic activity features. We then design a graph optimization module to infer C, which is used to refine A and B, ultimately generating B. Notably, ASGM learns the activity-related graphs across different time periods in a parameter-sharing manner, avoiding redundant parameters and improving modeling efficiency. By integrating activity information into spatial graph convolutions, ASGM achieves robust­ ness against varying activity patterns and enables mutualities between spatial and temporal information. Additionally, by combining ASGM with Temporal Multi-branch Graph Convolution Module (TMGM), we construct an Activity Aware Spatio­ Temporal Multi-branch Graph Convolutional Neural Network (ASTM-Net) for skelecton-based activity recognition. Exper­ imental results on the different datasets demonstrate that the proposed ASTM-Net outperforms State-Of-The-Art (SOTA) methods, validating its effectiveness.

The primary contributions of this paper are summarized as follows:

1)	We propose a novel ASGM that dynamically models 3A-Graphs, capturing temporal node affinities and integrating them into spatial graph convolutions to enhance robustness against varying activity patterns.

2)	We design a 3A-Graph framework comprising three components: an initialized graph based on physical connections, a trainable graph optimized during training, and a dynamically inferred activity-related graph. This framework enables the efficient representation of dynamic node affinities over time.

3)	Building upon ASGM, we develop ASTM-Net, which integrates ASGM with the TMGM to model multi-scale temporal features effectively.

## II.  Related works

In the field of HAR, researchers have explored various modalities such as RGB images, optical flow, and skeletal data. Among these, the skeletal modality, which represents the human body topology with nodes and bones, demonstrates greater stability when dealing with complex environments, including variations in lighting, viewpoint, and speed. As a result, skelecton-based activity recognition has become a key area of focus in recent studies. With the rapid advance­ ments in deep learning, methods leveraging ConvNets, RNNs, and GCNNsfor skelecton-based activity recognition have emerged. Table 1 summarizes the advantages and disadvantages of some representative approaches.

## A.  Skelecton-based activity recognition with convnets

ConvNets have been applied to skelecton-based activity recognition using two main approaches. The first approach treats the raw keypoint coordinate data (i.e., x, y, z) as RGB channels of an image, mapping the skelecton data into a three-channel format and using ConvNet models for classification. Li et al. [15] proposed a dataset-independent and translation-scale-invariant mapping method, converting 3D skelecton data into color images with guaranteed invariance in scale. To fully extract skelecton features, Xie et al. [16] introduced a dual-stream ConvNet model that considers both node and bone features, employing asymmetric convolution blocks to mitigate deformation effects in skelecton trajectories. The second approach involves custom-mapping activity and temporal information from skelecton data into color images and classifying these withConvNets. Hożyń et al. [31] defined custom distance features based on skelecton data, mapping them into textured color images and training the model with AlexNet. To better incorporate temporal information, Younsi et al. [32] proposed Joint Trajectory Maps (JTMs), which encode spatiotemporal node trajectory information as three texture images from front, side, and top views for activity recognition.

However, ConvNet-based methods in skelecton activity recognition often simplify skelecton information into image representations, limiting feature learning to adjacent nodes within a convolution kernel [33]. This approach neglects latent linkages among all nodes.

## B.  Skelecton-based activity recognition with RNNS

RNNs are adept at extracting long-term sequential information, making them suitable for processing skeletal activity data as temporal trajectories where node coordinates change over time. Kaseris et al. [17] partitioned the human skelecton into

**Table 1.  Summary of the advantages and disadvantages of representative methods.**

| Methods | Representative Works | Advantages | Disadvantages |
| --- | --- | --- | --- |
| ConvNet-based | Li et al. [15], Xie et al. [16] | Efficient modeling of local node relationships using established convolutional structures. | Forcefully mapping non-Euclidean skeleton data into images loses global node relations; limited receptive field. |
| RNN-based | Kaseris et al. [17], Feng et al. [18] | Good at capturing long-term dependencies, suitable for continuous action modeling. | Weak spatial modeling capability, unable to effectively express complex topological relationships between nodes. |
| Spectral GCNNs | ST-GCNN [19], ChebyNet [20] | Theoretically rigorous, global feature aggregation through graph Fourier transform. | Relies on fixed graph Laplacian matrix, unable to model dynamically; high computational complexity. |
| Spatial GCNNs | DCNN [21], GAT [22] | Direct aggregation of spatial neighbor features, supports dynamic graph structures, computationally efficient. | Manually defined neighbor rules may ignore long-distance node dependencies (e.g., hand collaboration actions). |
| Dynamic Graph | DGCN-MPA [23], HAM-HGNet [24] | Dynamically adjusts node relationships, adapts to changes in actions (e.g., differences in movement speed). | Dynamic graph generation module increases the number of parameters, prone to overfitting small datasets. |
| Attention-enhanced | CBAM-STGCN [25], KDS-GCN [26] | Enhances the representation of key nodes/ channels through attention mechanisms (e.g., importance of hand nodes in ‘throwing’). | Attention computation introduces additional overhead. |
| Hybrid Architectures | Wu et al. [27], Mansouri et al. [28] | Combines CNN (temporal) and GCN (spatial) to improve multimodal feature representation. | Dual-branch design leads to parameter redundancy, difficult to deploy on edge devices. |
| Transformer-based | SkateFormer [29], HCTransformer [30] | Self-attention mechanism captures global spatiotemporal dependencies, overcoming the locality limitation of graph convolution. | High computational complexity, large memory consumption for long sequences. |

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 4 / 30 five parts and arranged the node coordinates into long vectors for input into Long Short-Term Memory (LSTM) networks for activity recognition. Recognizing that some activities only involve a few nodes, Feng et al. [18] proposed an end-to-end spatiotemporal attention network using RNNs, focusing on critical frames and key nodes. However, the spatial modeling limitations of RNNs generally prevent these methods from achieving competitive results [34].

C.  Skelecton-based activity recognition with GCNNS

In recent years, graph convolution techniques have advanced significantly, and skeletal data, inherently non-Euclidean, naturally aligns with graph structures where nodes represent nodes. Compared to ConvNets and RNNs, GCNNs can simultaneously model spatial and temporal affinities, drawing increasing attention from researchers. The core idea is to aggregate edge information to update node representations. GCNNs excel in learning from data with graph topologies and are well-suited for modeling non-Euclidean spatial data. GCNN methods are broadly classified into spectral-based and spatial-based approaches.

a.  Spectral-based GCNNs.  Classical convolution kernels require fixed neighborhood sizes around the central node, which is challenging for graph-structured data due to variable and unordered node neighborhoods. Spectral-based GCNNs leverage graph signal processing, using Fourier transforms to convert graph signals into the frequency domain for convolution operations and then back to the spatial domain via inverse Fourier transforms [35], as shown in Fig 1.

Examples include the first-generation GCNN [10], Chebyshev Networks (ChebyNet) [20], and first-order approximations of ChebyNet [21]. The first-generation GCNN’s reliance on Laplacian matrix eigendecomposition leads to high computa­ tional costs, limiting practical use. To address this, ChebyNet approximates convolution kernels with Chebyshev polynomi­ als, greatly improving efficiency. Xu et al. [36] further simplified ChebyNet with a first-order approximation, represented as:

$$
H^{( l + 1 )} = \sigma ( D ˜ – 1/2_{A} ˜ D ˜ – 1/2_{H} ( l )_{W} ( l )_{)} \tag{1}
$$

where  ̃A = A + I_{N} is the adjacency matrix with self-loops, I_{N} is the identity matrix,  ̃D is the degree matrix, W^{(l)} denotes the trainable weight matrix for layer l, \sigma(.) is the nonlinear activation function, and H^{(}^{l}^{)} represents features at layer l with input H = X.

b.  Spatial-based GCNNs.  Spatial-based GCNNs eliminate affinity on graph spectral theory, instead aggregating information from neighboring nodes to update central nodes from a spatial perspective [22,37]. These methods avoid Laplacian matrix constraints, enabling applications to directed graphs. Spatial-based GCNNs, akin to extended ConvNets, perform weighted summation of node information to achieve convolution [38]. Steps include propagating node features to neighbors, aggregating neighborhood features, and applying linear and nonlinear transformations to enhance model expressiveness. Examples include Diffusion Convolutional Neural Networks (DCNN) [26], Graph Sample and Aggregate (GraphSAGE) [39], and Graph Attention Networks (GAT) [40]. DCNN controls information flow via transition probabilities, GraphSAGE uses random sampling to aggregate features, and GAT employs attention coefficients to update node features, offering diverse methods for graph topology convolution. Recent advancements focus on enhancing spatial modeling through dynamic graph topologies and attention mechanisms, as follows:

![Fig 1.  The system of spectral-based GCNNs.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p5_1.png)

*Fig 1.  The system of spectral-based GCNNs.*

1)	Dynamic Graph Construction: Huang et al. [23] proposed dynamic graph convolutional networks with multi-scale posi­ tion attention (DGCN-MPA), adaptively fusing hierarchical attention to adjust node relationships across scales. Yang et al. [24] designed a hierarchical adaptive multi-scale hypergraph (HAM-HGNet) that clusters joints into parts based on movement patterns, relaxing fixed topology constraints.

2)	Knowledge & Attention Integration: Roy et al. [41] introduced knowledge-driven shift-GCN (KDS-GCN), leveraging graph connectivity priors and coordinate features to enrich representations. Qin et al. [25] enhanced ST-GCN with con­ volutional block attention modules (CBAM-STGCN), refining spatial-channel features through adaptive weighting.

3)	Hybrid Architectures: To bridge Euclidean and non-Euclidean modeling, Wu et al. [27] combined multi-channel CNNs with GCNs, where CNNs capture local temporal patterns and GCNs extract spatial dependencies. Mansouri et al. [28] similarly fused CNNs and GCNs to jointly learn spatiotemporal dynamics.

4)	Transformer-Based Extensions: Addressing GCNs’ limited receptive fields, Do et al. [29] proposed SkateFormer, parti­ tioning skeletal-temporal relations for memory-efficient self-attention. Lin et al. [30] developed HCTransformer, decou­ pling human-centric and context features through domain-invariant interaction learning.

Furthermore, recent advances in graph neural networks across diverse domains have inspired novel skeleton-based HAR designs. For example, Su et al. [42] introduced MFEn-GFDn, a Multi-Feature Extraction Network and Graph Fusion Detection Network, to enhance radar target detection in complex sea clutter by constructing multi-feature graph data and applying graph fusion strategies. Zhang et al. [43] demonstrated the integration of GNNs with brain functional network analysis, highlighting the potential of interpretable GNN architectures for large-scale, heterogeneous graphs in clinical neuroscience applications. In the realm of multimodal video analysis, Wang et al. [44] proposed a Geo-based two-stream framework that builds facial graphs and fuses GCN and CNN features alongside temporal attention, achieving robust per­ sonality trait prediction in short video clips. These works underscore the versatility of GNNs in capturing complex relational patterns, motivating their application to dynamic skeleton activity graphs in HAR.

## III.  Methodology

A.  Definitions

a.  Construction of the skelecton graph.  Given a human skelecton, let N represent the number of nodes. The skelecton is naturally abstracted as a graph, where a skeleton with N nodes is represented as an undirected graph G=(V,E). Here, V={v_{i}|i = 1,2,...,N} represents all vertices of the skelecton graph, corresponding to the nodes of the skelecton, and E represents the edges of the graph, corresponding to the physical connections between nodes. The affinity relationships between nodes are encoded into an adjacency matrix  ̃A of size N*N, with elements defined as:

$$
{ 1, (i = j) or (v_{i}&v_{j}are connected) 0, otherwise
$$

̃A^{ij} =

(2)

b.  Implementation of traditional graph convolution.  Based on the constructed skelecton graph, ST-GCNN (Spatiotemporal graph convolutional neural network) [19] defines the implementation of graph convolution on skeletal data. Given an input feature map f_{in}  \in  R^{C}in∗T∗N, where C_{in} represents the number of input channels and T represents the number of frames, the process of graph convolution on skelecton data is expressed as:

$$
f_{out} =_{\sum_{k = 1}}^{K} W_{k} f_{in} ( A_{k_{⊙}} L ) \tag{3}
$$

where K is the number of spatial subsets, set to 3 in ST-GCNN. A_{k} = Λ–1/2 k

̃A_{k}Λ–1/2 k

represents the normalized adjacency

N \sum  j=1

̃A^{ij}

k + \lambda is the normalized diagonal matrix, with \lambda = 0.001 to prevent empty rows in  ̃A_{k}. Note that

matrix, and Λ_{k} =

N \sum  j=1

̃A_{k} =  ̃A. W_{k}  \in  R^{C}out∗C_{in} is the trainable weight matrix, where C_{out} represents the number of output channels. L  \in  R^{N}∗N

is a trainable matrix initialized with all elements set to 1. The operator ⊙ denotes the Hadamard product (element-wise multiplication). Using formula (3), the spatial graph convolution output f_{out}  \in  R^{C}out∗T∗N can be obtained.

B.  ASGM

The framework of the proposed ASGM is illustrated in Fig 2.

The process consists of three main stages:

1)	Extract semantic features of activity information.

2)	Dynamically infer a activity-related graph to capture the pairwise affinities among nodes across different time periods and optimize the skelecton graph.

3)	Perform graph convolution using the optimized adjacency graph to obtain the final ASGM output.

Accordingly, ASGM consists of three components:

1)	Activity Information Extraction Block (Fig 2): This block is implemented using a transformation function T(.) and an extraction function E(.).

2)	Graph Optimization Block (Fig 3): This block includes an inference function D(.) and an optimization function O(.).

(3)	ASGM Implementation Block: The optimized adjacency graph is used to perform graph convolution, producing the final

output.

a.  Activity information extraction block.  Before a graph can adapt to the choreography of a moving body, the model needs a succinct summary of how that body is currently evolving. Raw joint coordinates alone are too literal; they tell us where the joints are but not why they are there. By first translating the input tensor through a low‐rank linear bottleneck, we distil high‐variance motion cues—speed, directional coherence, local synchrony—into a compact semantic vector. The subsequent frame‐to‐frame differencing then accentuates precisely those temporal gradients that classical GCNN layers tend to miss. In short, this block converts unstructured spatial snapshots into a trajectory‐aware “action fingerprint” that downstream modules can reason over.

As shown in Fig 3, the purpose of the activity information extraction block is to obtain a semantic representation of activity information. For a given input feature f_{in}  \in  R^{C}in∗T∗N, the transformation function T(.) is applied to transform the input features. To reduce model complexity and computational resource requirements, a simple linear transformation with a reduction ratio r is adopted for T(.), which is expressed as:

$$
P = T ( f_{in} ) = W_{1} f_{in} \tag{4}
$$

where P  \in  R^{C}in/r∗T∗N represents the semantic features obtained from the input features, and W_{1}  \in  R^{C}in/r∗C_{in} is the weight matrix.

Based on the semantic features P, activity features M  \in  R^{C}in/r∗T∗N are further extracted through the extraction function E(.). As shown in the Fig 2, the activity information is obtained by calculating the difference between adjacent frames of the semantic features, and all frame-level activity information is concatenated along the temporal dimension to form M. The process is defined as:

![Fig 2.  Overall framework of the proposed ASGM. The module extracts semantic features of activity information, dynamically infers an activity-­ related adjacency graph (3A-Graph), and then applies spatial graph convolutions using the optimized adjacency graph to model activity-specific spatial relationships.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p8_1.png)

*Fig 2.  Overall framework of the proposed ASGM. The module extracts semantic features of activity information, dynamically infers an activity-­ related adjacency graph (3A-Graph), and then applies spatial graph convolutions using the optimized adjacency graph to model activity-specific spatial relationships.*

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 8 / 30 https://doi.org/10.1371/journal.pone.0324605.g003

![Fig 3.  Detailed structure of the activity information extraction block within ASGM. This block generates semantic representations by computing temporal differences between adjacent frames of transformed features, capturing meaningful motion patterns crucial for subsequent dynamic graph inference.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p9_1.png)

*Fig 3.  Detailed structure of the activity information extraction block within ASGM. This block generates semantic representations by computing temporal differences between adjacent frames of transformed features, capturing meaningful motion patterns crucial for subsequent dynamic graph inference.*

$$
M = E ( P ) = concat ( tanh ( P_{t + 1} – P_{t} ) ) , t = 1 , 2 , ... , T – 1 \tag{5}
$$

where concat(.) denotes concatenation, tanh(.) represents the hyperbolic tangent function that maps outputs to (-1,1), and P_{t} denotes the semantic features of the t-th frame.

b.  Graph optimization block.  A skeleton graph is only useful if its edges mirror the latent biomechanics of the action at hand. Relying on a single, anatomically predefined adjacency matrix risks freezing the graph in a posture that may be irrelevant—or even misleading—once the motion unfolds. Our optimisation strategy therefore treats the graph as a living document: we start with hard‐wired physical links, overlay a learnable canvas, and finally let data‐driven activity affinities rewrite the margins in real time. The key idea is to let motion‐dependent similarity matrices pull or relax edges, so that jumping contracts the ankle–knee–hip triad while clapping cross‐links the two wrists. This dynamic tri‐graph fusion produces an adjacency structure that breathes with the action yet stays tethered to plausible human kinematics.

In the k-th spatial subset, the 3A-Graph consists of three components, i.e., A_{k}, B_{k}, and C_{k}. As illustrated in Fig 4, the adjacency matrix A_{k} and trainable matrix B_{k} are shared across all frames, making it difficult to capture the dynamic changes in the skeletal graph over time. To model the temporal affinities between nodes at different time periods, the extracted activity features are used to infer a activity-related graph C_{k}  \in  R^{s}∗N∗N, where s represents the number of time segments. C_{k} is then used to optimize A_{k} and B_{k}, resulting in the 3A-Graph G_{k}  \in  R^{s}∗N∗N.

Given the extracted activity features M  \in  R^{C}in/r∗T∗N, it is first divided into s feature segments along the temporal dimen­ sion, denoted as M_{i}, where i = 1,2,...,s. Each segment has a shape of C_{in}/r ∗ T/s ∗ N. Next, two embedding functions \theta and φ are applied to transform the shape of each segment to C_{out} ∗ T/s ∗ N. To ensure efficiency in modeling the activity-­ related graph, \theta and φ share weights across all feature segments, and the process is defined as:

$$
\theta ( M_{i} ) = W_{2} M_{i} , i = 1 , 2 , ... , s \tag{6}
$$

$$
ϕ ( M_{i} ) = W_{3} M_{i} , i = 1 , 2 , ... , s \tag{7}
$$

![Fig 4.  Detailed structure of the graph optimization block within ASGM. This block dynamically constructs the 3A-Graph by integrating three com­ ponents: a manually initialized adjacency graph based on physical node connections (A), a trainable graph optimized during network training (B), and a dynamically inferred activity-related graph (C), effectively modeling temporal variations in node affinities.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p10_1.png)

*Fig 4.  Detailed structure of the graph optimization block within ASGM. This block dynamically constructs the 3A-Graph by integrating three com­ ponents: a manually initialized adjacency graph based on physical node connections (A), a trainable graph optimized during network training (B), and a dynamically inferred activity-related graph (C), effectively modeling temporal variations in node affinities.*

where W_{2}  \in  R^{C}out∗C_{in}/r and W_{3}  \in  R^{C}out∗C_{in}/r are the weight matrices of \theta and φ, respectively. As shown in Fig 2, \theta and φ are implemented using two separate 1*1 convolution layers. The resulting embedded features \theta(M_{i}) and φ(M_{i}) both have a shape of C_{out} ∗ T/s ∗ N.

The shapes of \theta(M_{i}) and φ(M_{i}) are then reshaped to N ∗ C_{out}T/s and C_{out}T/s ∗ N, respectively, and the activity-related graph C_{k} is inferred using the inference function D(.). By multiplying the reshaped matrices, a similarity matrix is obtained, where each element represents the similarity between any two nodes. To enrich the feature representation, two distinct branches are used to calculate feature similarity globally, avoiding over-reliance on self-connections and enhancing subsequent optimization. The similarity matrix is normalized using the Softmax function to scale values into (0,1). Each feature segment M_{i} corresponds to a similarity matrix, and concatenating all similarity matrices produces C_{k}  \in  R^{s}∗N∗N. As shown in the Fig 4, C_{k} is defined as:

$$
C_{k} = c ( D ( \theta ( M_{i} ) , ϕ ( M_{i} ) ) ) = c ( Softmax ( \theta ( M_{i} )_{∗} ϕ ( M_{i} ) ) ) , i = 1 , 2 , ... , s \tag{8}
$$

Finally, the activity-related graph C_{k} is used to optimize the initialized matrix A_{k} and trainable matrix B_{k}, producing the 3A-Graph G_{k}  \in  R^{s}∗N∗N. The optimization function O(.) is defined as:

$$
G_{k} = O ( A_{k} , B_{k} , C_{k} ) = A_{k} + B_{k} + \alpha_{k} C_{k} \tag{9}
$$

where A_{k} is as defined in formula (1); B_{k} is initialized as a trainable matrix with all elements set to 0, optimized jointly with the network in an end-to-end manner; and \alpha_{k} is a trainable parameter that adjusts the relative importance of C_{k} compared to A_{k} and B_{k}. The element-wise addition is performed across all s time segments.

**Algorithm 1: Details the dynamic optimization process, integrated into ASGM’s forward pass.**

**Algorithm 1: Details the dynamic optimization process, integrated into ASGM’s forward pass.**
```text
Algorithm 2. ASTM-Net.
Input: Input features F \in ℝ {T \times N \times C} ; Initialized graph A \in ℝ {N \times N} ; Trainable graph B \in ℝ {N \times N} ; Segments s;
reduction ratio r
Output: Optimized graph G \in ℝ {N \times N}
```

Procedure: 1.  # Activity feature extraction (Eq. 4–5) P = Linear(C  \to  C/r)(F) # Eq. 4, T(·) M = Concat([tanh(P{t + 1} - P_{t}) for t in 0:T-1]) # Eq. 5, E(·) 2.  # Split into s temporal segments Msegments = Split(M, s) # M_{i}  \in  R{N  \times  (T/s)  \times  (C/r)}

3. # Compute activity-related graph C C = [] for M_{i} in Msegments: \theta = Conv1D(C/r  \to  C/(2r))(Mi) # \theta(Mi) φ = Conv1D(C/r  \to  C/(2r))(Mi) # φ(Mi) S = MatMul(\theta, φ.transpose(1,2))/ sqrt(d’) C_{i}= Softmax(S, dim = -1) # Eq. 8

![Figure p.11](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p11_1.png)

$$
\begin{aligned} 4. #^{C &=} Fuse^{Stack} A^{(} ,^{C )} B ,^{#} C^{C} \\ G_{G} &=_{=} A_{LayerNorm} + B + \alpha * ( G ) \end{aligned} \frac{( Eq.^{ℝ} 9 )}{ReduceSum (} C , dim = 0 )
$$

c.  ASGM implementation block.  After the graph has morphed into an activity‐aware scaffold, the final step is to project rich node features across this scaffold without drowning in parameters. Splitting the temporal horizon into coarse segments—and using the same 3A‐Graph within each—creates a repeating canvas on which motion patterns can be painted at multiple rhythms, but without replicating weights. By summing the outputs of three complementary spatial subsets we emulate multi‐head attention: each subset selects a different anatomical or functional perspective (self‐loops, limb‐centric edges, cross‐limb shortcuts). The result is a lean yet expressive convolution that captures both the where and the how fast of human motion in a single sweep.

As shown in the Fig 2, given the input skeletal features f_{in} and the 3A-Graph G_{k}, a 2D convolution layer with a kernel size of 1 is first applied to transform f_{in}. Simultaneously, G_{k}  \in  R^{s}∗N∗N is divided into s 3A-Graph G_{ki}  \in  R^{N}∗N, i = 1, 2, ..., s.

Each G_{ki} is used to perform spatial graph convolution for each time period. The spatial graph convolutions across all time periods are fused via summation to produce the activity aware graph convolution result for the k-th spatial subset. Assum­ ing K = 3 spatial subsets, the final ASGM output is obtained by summing the results of all K spatial subsets. The process is expressed as:

 \sum K

 \sum s

f_{out} =

$$
s_{i = 1^{W_{k} f_{in} G_{ki}}} \tag{10}
$$

k=1

where W_{k}  \in  R^{C}out∗C_{in} is the weight matrix, and f_{out}  \in  R^{C}out∗T∗N represents the output of ASGM.

C.  ASTM-net

Building upon ASGM, this paper proposes ASTM-Net. As shown in Fig 5, for a given 3D skelecton trajectory, ASTM-Net con­ sists of 12 SpatioTemporal Graph Convolutional Blocks (STGCBs) to extract features from the ASTM-Net. The extracted fea­ tures are then aggregated using Global Average Pooling (GAP), and the activity class is predicted using a Softmax classifier.

The structure of the STGCB is illustrated in Fig 6. It comprises an ASGM layer, an TMGM layer, and residual connec­ tions, with Batch Normalization (BN) and ReLU activation applied. Specifically, to model multiple diverse scale temporal features, we design the TMGM based on the temporal modeling component in [45]. As shown in Fig 7, TMGM includes four branches, where each branch begins with a 1*1 convolution layer to reduce the number of channels. Specifically, the first two branches use temporal dilated convolutions with a fixed kernel size of 5*1 but with two different dilation factors to expand the receptive field. The third branch uses a 1*1 convolution layer followed by a max pooling operation. The fourth branch applies a standalone 1*1 convolution layer. Finally, the outputs from all four branches are concatenated to produce the output of TMGM. In ASTM-Net, the first four STGCBs output 64 channels. At the 5th and 8th STGCBs, the number of output channels is doubled, and the temporal dimension is downsampled with a stride of 2.

Within the ASTM-Net pipeline the TMGM sits immediately after ASGM inside every STGCB, acting as the temporal counterpart to ASGM’s dynamic spatial reasoning. Whereas ASGM restructures the graph to match the current action, TMGM ensures that the network views that action through several temporal lenses at once—capturing a finger-snap that vanishes in two frames, a hand-clap that spans half a second, or a standing-up motion that unfolds even more slowly.

Practically, TMGM routes the same input tensor through four parallel paths. Each path begins with a 1  \times  1 bottleneck that quarters the channel count, then applies a distinct temporal operation: (i) a dilated 5  \times  1 convolution with dilation 1 for short‐range nuances; (ii) the same kernel with dilation 3 to reach mid‐range rhythms; (iii) a 5‐frame max‐pool that spot­ lights the most salient joint activations; and (iv) a plain 1  \times  1 convolution that preserves raw timing details as a stabilising identity branch. The four outputs are concatenated, batch‐normalised, passed through ReLU, and finally compressed back to the original channel width before being forwarded to the next block.

This “multi‐branch” layout borrows the spirit of Inception and ResNeXt: each branch specialises in a different receptive field, so the fusion effectively ensembles several lightweight temporal experts without inflating either depth or FLOPs. By weaving TMGM organically into every STGCB, ASTM‐Net maintains a balanced dialogue between where joints are connected (via ASGM) and how fast they move (via TMGM), yielding a lean yet highly expressive framework for skele­ ton‐based activity recognition.

D.  Motivation for hybrid integration of ASGM and TMGM

The integration of ASGM with TMGM is driven by two fundamental challenges in skeleton-based activity recognition: (1) the need to jointly model dynamically evolving spatial node relationships and multi-scale temporal dependencies, and (2) the requirement to achieve this synergy without incurring prohibitive computational costs. Traditional approaches that process spatial and temporal features through isolated modules [11–14] create artificial boundaries between these dimensions, failing

![Fig 5.  Architecture of the proposed ASTM-Net. It comprises twelve stacked SpatioTemporal Graph Convolutional Blocks (STGCBs), followed by a Global Average Pooling (GAP) layer and a fully-connected layer with softmax activation for final activity classification.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p13_1.png)

*Fig 5.  Architecture of the proposed ASTM-Net. It comprises twelve stacked SpatioTemporal Graph Convolutional Blocks (STGCBs), followed by a Global Average Pooling (GAP) layer and a fully-connected layer with softmax activation for final activity classification.*

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 13 / 30 https://doi.org/10.1371/journal.pone.0324605.g006

![Fig 6.  Internal structure of the STGCB used in ASTM-Net. Each STGCB integrates ASGM for dynamic spatial feature extraction and a TMGM for capturing multi-scale temporal features, coupled with residual connections to enhance learning stability.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p14_1.png)

*Fig 6.  Internal structure of the STGCB used in ASTM-Net. Each STGCB integrates ASGM for dynamic spatial feature extraction and a TMGM for capturing multi-scale temporal features, coupled with residual connections to enhance learning stability.*

![Fig 7.  Detailed structure of the TMGM. It employs multiple parallel branches with different dilation rates (dilated convolutions) and pooling operations to capture temporal information at varying scales, improving the model’s capability to represent diverse temporal dynamics within human activities.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p14_2.png)

*Fig 7.  Detailed structure of the TMGM. It employs multiple parallel branches with different dilation rates (dilated convolutions) and pooling operations to capture temporal information at varying scales, improving the model’s capability to represent diverse temporal dynamics within human activities.*

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 14 / 30 to capture critical cross-spatiotemporal correlations. For instance, the importance of spatial node connections (e.g., hand-­ elbow coordination in a “throwing” action) inherently depends on their temporal evolution (e.g., acceleration patterns during the wind-up phase). ASGM and TMGM address these limitations through complementary mechanisms:

a.  Complementary spatial-temporal modeling.  ASGM specializes in adaptive spatial feature extraction by constructing dynamic 3A-Graphs that evolve with activity patterns. Unlike static adjacency matrices in conventional GCNNs [19], the 3A-Graph’s activity-related component (C-Graph) explicitly links spatial node affinities to temporal motion cues through cross-frame similarity learning (i.e.,(8)). This enables localized adaptation to activity-specific interactions, such as strengthening hand-shoulder connections during “overhead press” motions while weakening them in “kicking” actions. However, spatial adaptations alone cannot resolve temporal ambiguities in similar motion phases, e.g., distinguishing the acceleration phase of “jumping” from the deceleration phase of “landing.”

TMGM addresses this through multi-scale temporal modeling via parallel branches with varied receptive fields (Fig 7). The dilated convolution branches (d = 1,3) capture both micro-motion details (e.g., finger tremors during “writing”) and macro-motion trends (e.g., full-body coordination in “falling”), while the pooling branch suppresses transient noise. Cru­ cially, TMGM operates on ASGM-refined spatial features, allowing temporal operators to leverage activity-aware spatial contexts. This bidirectional synergy enables ASTM-Net to simultaneously answer:

1)	Spatial “Where”: Which nodes are critically interacting at this temporal scale?

2)	Temporal “When”: How do these interactions evolve across motion phases?

b.  Efficiency through structural cohesion.  The hybrid design achieves parameter efficiency through shared computation across modules. ASGM’s activity-related graph inference ((i.e., (6)-(8)) reuses temporal difference features (i.e., (5)) that TMGM subsequently processes, avoiding redundant feature extraction. Meanwhile, TMGM’s multi-branch outputs are aggregated before feeding into the next ASGM layer, ensuring progressive refinement of both spatial and temporal features without channel explosion.

E.  Algorithm flowchart

The overall algorithm workflow of ASTM-Net is illustrated in the following Algorithm 2.

**Algorithm 2: ASTM-Net.**
```text
Input: 
Raw 3D skeleton sequences; Each sequence contains 3D joint coordinates over time.
Output: 
Predicted activity category for each input sequence
```

Procedure: Step 1: Input Skeleton Preprocessing 1.1 Normalization and Resizing: - Normalize raw 3D skeleton sequences to hip-centric coordinates. - Resize the sequence to 64 frames using linear interpolation. 1.2 Feature Initialization: - Initialize node features with the 3D coordinates (x, y, z). - Compute motion vectors (Δx,Δy, Δz) and include them in the node features. Step 2: Dynamic 3A-Graph Construction 2.1 Activity Information Extraction: - For each frame, extract semantic features using a linear transformation (refer to Equation 4). - Calculate the temporal differences of these features (refer to Equation 5) to capture motion patterns. 2.2 Graph Optimization: - Dynamically infer the activity-related graph Ck via cross-temporal similarity learning (Equa­ tions 6–8).

- Fuse the physical graph Ak, trainable graph Bk, and the activity-related graph Ck to generate
the final adjacency graph Gk (Equation 9).
Step 3: SpatioTemporal Graph Convolution
### 3.1 ASGM Module:
- Apply spatial graph convolution on the optimized 3A-Graph.
- Aggregate node features across K = 3 spatial subsets (refer to Equation 10).
### 3.2 TMGM Module:
- Extract multi-scale temporal features using four parallel branches (e.g., dilated convolution,
pooling, etc.).
- Concatenate the outputs of these branches to enhance temporal modeling.
Step 4: Hierarchical Feature Aggregation
### 4.1 Layer-wise Feature Extraction:
- Process features through 12 STGCB layers.
- Apply progressive downsampling with a stride of 2 at the 5th and 8th blocks to increase the
receptive field.
### 4.2 Global Feature Pooling:
- Apply Global Average Pooling (GAP) to aggregate the spatiotemporal features into a compact
feature vector.
Step 5: Activity Classification
### 5.1 Final Prediction:
- Feed the pooled feature vector into a Softmax classifier to predict the activity category.

## IV.  Experiment

A.  Dataset

a.  NTU_RGB_plus_D.  This widely-used large-scale skelecton dataset is collected using three horizontally placed Microsoft Kinect v2 cameras and contains 56,880 samples covering 60 daily and health-related activities [46]. The dataset includes 40 subjects, and each activity is performed by one or two people. The human skelecton in each sample is represented by 25 3D nodes. Two official benchmarks are provided:

1)	X-Sub: The 40 subjects are partitioned into 20 for training (37,920 samples) and 20 for testing (18,960 samples). From the training set, 10% (3,792 samples) are randomly selected as the validation set for hyperparameter tuning.

2)	X-View: Data from cameras 2 and 3 (37,920 samples) are used for training, with 10% (3,792 samples) reserved for validation, while data from camera 1 (18,960 samples) serve as the test set.

b.  NTU_RGB_plus_D_120.  This dataset is an extension of NTU_RGB_plus_D, containing 112,954 samples across 120 activity categories [47]. The number of subjects increases to 106, and the number of cameras rises to 32. Two official benchmarks are provided:

1)	X-Sub: 50 subjects (53,230 samples) are designated for training, with 10% (5,323 samples) held out for validation, and the remaining 56 subjects (59,724 samples) for testing.

c.  Toyota smarthome.  Toyota Smarthome [48,42] is collected in an apartment with 7 Kinect v1 cameras, recording 31 daily activities (e.g., “drink from cup,” “read book”) performed by 18 elderly subjects (ages 60–80). The Samples include 16,115 video clips with RGB, depth, and 3D skeleton modalities (18 joints per frame). Evaluation Protocols are provided:

CV1: Train on front-view (dining room), test on side-view. CV2: Train on mixed views, test on front-view.

B.  Experiment settings

All experiments in this paper are conducted using the Tensorflow deep learning framework on an NVIDIA GeForce RTX 4070 Ti GPU. The model is optimized using the Adam (Adaptive Moment Estimation) algorithm with the initial learning rate of 0.9, the first moment decay rate (i.e., \beta_{1}) of 0.9, the first moment decay rate (i.e., \beta_{2}) of 0.999, the numerical stability term (i.e., ∊) of 1e-8. ASTM-Net is trained for 80 epochs on both the NTU_RGB_plus_D and NTU_RGB_plus_D_120 datasets. A warm-up strategy is applied for the first 10 epochs to stabilize the training process. The subsequent learning rate is reduced to 1/10 at epochs 40 and 60. The batch size is set to 32, and the parameters r and s are set to 8 and 4, respec­ tively. Due to the redundancy of skeletal data in the temporal dimension, the skelecton trajectories are resized to 64 frames using the preprocessing method from [49].

C.  Comparative experiment

Current mainstream methods often adopt multi-stream fusion frameworks. For a fair comparison, we use the same ensemble strategy as in [41,25], where the final model combines the results from node stream, bone stream, node&ac­ tivity streams, and bone&activity streams. The results of ASTM-Net on the NTU_RGB_plus_D dataset and NTU_RGB_ plus_D_120 dataset are shown in Tables 2, respectively. For all models, results are reported for:

1)	*-Ns: Using only the Node stream (Ns).

2)	*-NBs: Using both the Node & Bone streams (NBs).

3)	*-ALLs: Using all four streams.

Three key conclusions can be drawn from Table 2:

1)	Efficiency and Lightweight Design: ASTM-Net is a lightweight and efficient method among multi-stream approaches. Notably, the proposed ASTM-Net-ALLs model has 51.9% fewer parameters compared to DualHead-Net-ALLs [53], which achieved the highest accuracy in prior methods [19,45,23,24,51]. Moreover, the FLOPs of ASTM-Net-ALLs are 49.8% lower than those of MST-GCNN-ALLs [54] with similar recognition performance, demonstrating that the pro­ posed ASTM-Net achieves high accuracy with lower computational cost.

2)	Superior Performance: Our ASTM-Net outperforms other methods across all benchmarks on both datasets. On the NTU_RGB_plus_D dataset, ASTM-Net-ALLs achieves recognition accuracies of 92.28% (X-Sub) and 96.65% (X-View). On the NTU_RGB_plus_D_120 dataset, ASTM-Net-ALLs achieves the best results with accuracies of 88.79% (X-Sub) and 90.15% (X-Set).

To comprehensively evaluate the trade-off between accuracy and computational cost, we compare ASTM-Net with three representative GCNN variants: Shift-GCNN [54], MST-GCNN [41], and DualHead-Net [53]. We analyze their perfor­ mance, model size, memory footprint, and training efficiency on the NTU-RGB + D X-Sub benchmark.

From Table 3: 1)  Accuracy vs. Parameters.  ASTM-Net achieves 0.31% higher accuracy than DualHead-Net-ALLs with 51.9% fewer parameters, demonstrating the efficiency of its dynamic 3A-Graph parameter sharing. Compared to Shift-GCNN-ALLs,

**Table 2.  Comparative Experimental Results On Two Datasets. Where D Indicates The Ntu_Rgb_Plus_D Dataset And D_120 Indicates The NTU_RGB_PLUS_D_120 Dataset. Where The Arrow Pointing Up Means The Larger The Result Is Better, And The Arrow Pointing Down Means The Smaller The Result Is Better.**

<table>
  <tr><th colspan="2">The Smaller The Result Is Better.</th></tr>
  <tr><td>Method</td><td>X-Sub (D)↑</td><td>X-View (D)↑</td><td>X-Sub (D_120)↑</td><td>X-Set (D_120)↑</td><td>#Params/M ↓</td><td>#FLOPs/ G↓</td></tr>
  <tr><td>Sighencea et al. [50]</td><td>81.45%</td><td>88.21%</td><td>N/A</td><td>N/A</td><td>3.26</td><td>16.41</td></tr>
  <tr><td>Wu et al. [23]</td><td>88.48%</td><td>95.08%</td><td>N/A</td><td>N/A</td><td>7.15</td><td>37.39</td></tr>
  <tr><td>Zhang et al. [51]</td><td>88.92%</td><td>94.44%</td><td>79.16%</td><td>81.45%</td><td>1.44</td><td>0.94</td></tr>
  <tr><td>Shift-GCNN-Ns [26]</td><td>87.75%</td><td>95.02%</td><td>80.88%</td><td>83.15%</td><td>0.80</td><td>2.62</td></tr>
  <tr><td>Shift-GCNN-NBs [26]</td><td>89.62%</td><td>95.93%</td><td>85.25%</td><td>86.54%</td><td>1.75</td><td>5.09</td></tr>
  <tr><td>Shift-GCNN-ALLs [26]</td><td>90.69%</td><td>95.95%</td><td>85.88%</td><td>87.54%</td><td>3.33</td><td>10.10</td></tr>
  <tr><td>Liu et al. [52]</td><td>91.46%</td><td>96.13%</td><td>86.81%</td><td>88.35%</td><td>6.59</td><td>48.95</td></tr>
  <tr><td>Singh et al. [24]</td><td>91.47%</td><td>95.93%</td><td>87.28%</td><td>88.56%</td><td>N/A</td><td>N/A</td></tr>
  <tr><td>MST-GCNN-Ns [25]</td><td>88.93%</td><td>95.02%</td><td>82.77%</td><td>84.44%</td><td>3.10</td><td>10.67</td></tr>
  <tr><td>MST-GCNN-NBs [25]</td><td>91.04%</td><td>96.34%</td><td>86.98%</td><td>88.22%</td><td>6.00</td><td>21.26</td></tr>
  <tr><td>MST-GCNN-ALLs [25]</td><td>91.46%</td><td>96.58%</td><td>87.42%</td><td>88.78%</td><td>12.00</td><td>42.52</td></tr>
  <tr><td>Zhou et al. [27]</td><td>90.94%</td><td>96.36%</td><td>86.26%</td><td>87.72%</td><td>3.64</td><td>9.51</td></tr>
  <tr><td>DualHead-Net-Ns [28]</td><td>90.23%</td><td>96.02%</td><td>84.58%</td><td>85.83%</td><td>3.00</td><td>N/A</td></tr>
  <tr><td>DualHead-Net-NBs [28]</td><td>91.67%</td><td>96.45%</td><td>87.82%</td><td>89.02%</td><td>6.01</td><td>N/A</td></tr>
  <tr><td>DualHead-Net-ALLs [28]</td><td>91.97%</td><td>96.53%</td><td>88.17%</td><td>89.22%</td><td>12.00</td><td>N/A</td></tr>
  <tr><td>Zhu et al. [29]</td><td>89.56%</td><td>96.29%</td><td>N/A</td><td>N/A</td><td>29.22</td><td>24.55</td></tr>
  <tr><td>STF-Net-Ns [30]</td><td>88.73%</td><td>94.98%</td><td>N/A</td><td>N/A</td><td>1.86</td><td>N/A</td></tr>
  <tr><td>STF-Net-NBs [30]</td><td>90.74%</td><td>96.18%</td><td>N/A</td><td>N/A</td><td>4.47</td><td>N/A</td></tr>
  <tr><td>STF-Net-ALLs [30]</td><td>91.08%</td><td>96.42%</td><td>86.44%</td><td>88.14%</td><td>6.96</td><td>N/A</td></tr>
  <tr><td>ASTM-Net-Ns</td><td>89.85%</td><td>94.99%</td><td>84.43%</td><td>89.41%</td><td>1.44</td><td>5.34</td></tr>
  <tr><td>ASTM-Net-NBs</td><td>91.68%</td><td>96.18%</td><td>88.12%</td><td>90.03%</td><td>2.87</td><td>10.70</td></tr>
  <tr><td>ASTM-Net-ALLs</td><td>92.28%</td><td>96.65%</td><td>88.79%</td><td>90.15%</td><td>5.77</td><td>21.39</td></tr>
  <tr><td colspan="2">https://doi.org/10.1371/journal.pone.0324605.t002</td></tr>
  <tr><td colspan="7">Table 3. Accuracy-Computational Trade-Off Comparison. Peak Gpu Memory Usage During Training (Batch Size = 32). Total Hours To Converge</td></tr>
  <tr><td colspan="2">On Ntu-Rgb + D X-Sub (Rtx 4070 Ti).</td></tr>
  <tr><td>Method</td><td>X-Sub ↑</td><td>#Params/M↓</td><td>#FLOPs/G↓</td><td colspan="2">Memory (MB)↓</td><td>Training Time (h)↓</td></tr>
  <tr><td>Shift-GCNN-ALLs [50]</td><td>90.69</td><td>3.33</td><td>10.10</td><td>1,250</td><td>14.2</td></tr>
  <tr><td>MST-GCNN-ALLs [56]</td><td>91.46</td><td>12.00</td><td>42.52</td><td>2,980</td><td>28.5</td></tr>
  <tr><td>DualHead-Net-ALLs [51]</td><td>91.97</td><td>12.00</td><td>N/A</td><td>3,120</td><td>32.1</td></tr>
  <tr><td>ASTM-Net-ALLs</td><td>92.28</td><td>5.77</td><td>21.39</td><td>890</td><td>18.7</td></tr>
</table>

<table>
  <tr><th>Shift-GCNN-ALLs [50]</th><th>90.69</th><th>3.33</th><th>10.10</th><th>1,250</th><th>14.2</th></tr>
  <tr><td>MST-GCNN-ALLs [56]</td><td>91.46</td><td>12.00</td><td>42.52</td><td>2,980</td><td>28.5</td></tr>
  <tr><td>DualHead-Net-ALLs [51]</td><td>91.97</td><td>12.00</td><td>N/A</td><td>3,120</td><td>32.1</td></tr>
  <tr><td>ASTM-Net-ALLs</td><td>92.28</td><td>5.77</td><td>21.39</td><td>890</td><td>18.7</td></tr>
  <tr><td colspan="2">https://doi.org/10.1371/journal.pone.0324605.t003</td></tr>
  <tr><td colspan="6">ASTM-Net improves accuracy by 1.59% while using only 73.4% more parameters, validating the cost-effectiveness of its</td></tr>
  <tr><td>multi-branch design.</td></tr>
  <tr><td colspan="6">2) Computational efficiency. ASTM-Net reduces FLOPs by 49.7% compared to MST-GCNN-ALLs while achieving 0.82% higher accuracy. Despite lacking FLOPs data for DualHead-Net, ASTM-Net’s 53.6% shorter training time highlights</td></tr>
  <tr><td>its optimization advantages.</td></tr>
  <tr><td colspan="6">3) Memory footprint. ASTM-Net consumes 71.5% less memory than MST-GCNN-ALLs, enabled by the lightweight</td></tr>
  <tr><td colspan="6">TMGM module and shared 3A-Graphs. Even against Shift-GCNN-ALLs, ASTM-Net reduces memory usage by 28.8%,</td></tr>
  <tr><td colspan="2">critical for large-batch training.</td></tr>
</table>

## Hence, ASTM-Net strikes an optimal balance between accuracy and computational cost.

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 18 / 30

D.  Ablation experiment

Unless otherwise specified, all ablation experiments in this section are conducted on the NTU_RGB_plus_D dataset using the X-Sub benchmark with 3D node coordinates as input.

a.  ASGM ablation.  To validate the effectiveness of our ASGM, we construct a baseline model (referred to as Model-A) using the spatiotemporal graph convolutional unit of Sighencea et al. [50] as the STGCB in ASGM. As shown in formula (3), the spatial graph convolution in ST-GCNN combines a initialized adjacency graph and a trainable matrix L through the Hadamard product. In contrast, the proposed ASGM optimizes the initialized graph and the trainable matrix B using the activity-related graph, as defined in formula (9). For a fair comparison, the temporal convolutional layers in the baseline are replaced with TMGM, resulting in Model-B. Table 4 shows the experimental results, where:

“&TMGM” indicates replacing all temporal graph convolutions in the baseline with TMGM. “&ASGM-n” indicates replacing the first n spatial graph convolutions in Model-B with ASGM. From Table 4, it can be observed that replacing the temporal convolutional layers of ST-GCNN with TMGM yields better results with fewer parameters. Gradually replacing the first seven spatial graph convolutions of Model-B with ASGM (represented by Models C-F) shows a consistent improvement in validation accuracy, demonstrating the effectiveness and stability of ASGM. Notably, replacing a single spatial graph convolution in Model-B with ASGM improves the activity recog­ nition accuracy by 0.91% on the X-Sub benchmark, further validating the strong performance of ASGM.

b.  3A-Graph ablation.  As described earlier, the 3A-Graph G in ASTM-Net consists of three components: the initialized graph A, the trainable graph B, and the activity-related graph C. To evaluate the importance of each component, we manually remove one part of the topology graph in ASTM-Net (referred to as Model-\delta) and denote the results as Models \alpha-\gamma.

The results are shown in Table 5. It can be observed that the activity-related graph C significantly benefits activity recognition, as removing any part of the 3A-Graph adversely affects the performance of ASTM-Net. Combining all three components achieves the best performance.

The recognition accuracies for Models \alpha&\gamma are 89.65% and 89.44%, respectively, indicating that the activity-related graph C plays a more critical role than the initialized graph A. Compared to Model-\gamma, the superior performance of ASTM- Net-Complete validates the effectiveness of C in optimizing A and B.

c.  Hyper-parameter ablation.  This section evaluates the performance of ASTM-Net under different hyper-parameter settings, including the reduction ratio r and the number of feature segments s (i.e., the number of time periods). The results are presented in Table 6.

**Table 4.  ASGM Ablation Results.**

<table>
  <tr><th colspan="2">Table 4. ASGM Ablation Results.</th></tr>
  <tr><td>Model</td><td>Model-A</td><td>Model-B</td><td>Model-C</td><td>Model-D</td><td>Model-E</td><td>Model-F</td></tr>
  <tr><td>Method</td><td>Baseline</td><td>&amp;TMGM</td><td>&amp;ASGM-1</td><td>&amp;ASGM-3</td><td>&amp;ASGM-5</td><td>&amp;ASGM-7</td></tr>
  <tr><td>#Params/M↓</td><td>2.23</td><td>1.18</td><td>1.18</td><td>1.18</td><td>1.18</td><td>1.18</td></tr>
  <tr><td>X-Sub↑</td><td>86.78%</td><td>87.24%</td><td>88.15%</td><td>88.97%</td><td>89.17%</td><td>89.26%</td></tr>
  <tr><td colspan="2">https://doi.org/10.1371/journal.pone.0324605.t004</td></tr>
  <tr><td colspan="2">Table 5. 3a.Graph ablation results.</td></tr>
  <tr><td>Model</td><td>Model-\alpha</td><td>Model-\beta</td><td>Model-\gamma</td><td>Model-\delta</td></tr>
  <tr><td>Method</td><td>ASTM-Net Without A</td><td>ASTM-Net Without B</td><td>ASTM-Net Without C</td><td>ASTM-Net-Complete</td></tr>
  <tr><td>#Params/M↓</td><td>1.44</td><td>1.38</td><td>1.18</td><td>1.44</td></tr>
  <tr><td>X-Sub↑</td><td>89.65%</td><td>88.76%</td><td>89.44%</td><td>89.87%</td></tr>
</table>

**Table 6.  Hyper-parameter ablation results.**

<table>
  <tr><th colspan="3">Table 6. Hyper-parameter ablation results.</th></tr>
  <tr><th>Method</th><th>Baseline</th><th>ASTM-Net</th></tr>
  <tr><td>r</td><td>2</td><td>4</td><td>8</td><td>8</td><td>8</td><td>8</td><td>8</td><td>16</td></tr>
  <tr><td>s</td><td>1</td><td>1</td><td>1</td><td>2</td><td>4</td><td>8</td><td>16</td><td>1</td></tr>
  <tr><td>#Params/M↓</td><td>2.23</td><td>2.33</td><td>1.67</td><td>1.44</td><td>1.44</td><td>1.44</td><td>1.44</td><td>1.44</td><td>1.29</td></tr>
  <tr><td>X-Sub↑</td><td>86.78%</td><td>89.57%</td><td>89.68%</td><td>89.77%</td><td>89.57%</td><td>89.87%</td><td>89.35%</td><td>89.75%</td><td>89.27%</td></tr>
</table>

https://doi.org/10.1371/journal.pone.0324605.t006



1.29

89.27%

1)	Effect of r: Fixing s = 1, we gradually increase r up to 16. The results show that regardless of the value of r, ASTM- Net consistently outperforms the baseline on the validation set, confirming its robustness and stability as a feature extractor. When r is set to 4 or 8, ASTM-Net achieves higher activity recognition accuracy compared to other values of r. Specifically, setting r = 8 results in better accuracy than r = 4 while requiring fewer parameters.

2)	Effect of s: Fixing r = 8, we compare different values of s. By learning the activity-related graph at progressively finer granularity (increasing s), the results show that finer-grained graphs do not necessarily optimize the skeletal adjacency graph better. Given that the skelecton trajectories are preprocessed to 64 frames, setting s = 1 means using all frames to learn a single similarity matrix, while setting s = 16 means generating one similarity matrix per 4 frames. The results demonstrate that ASTM-Net achieves the highest accuracy when r = 8 and s = 4.

d.  Depth ablation.  To analyze how ASTM-Net scales with model depth and its computational trade-offs, we conduct ablation experiments on the NTU-RGB + D X-Sub benchmark, varying the number of STGCBs. The results are presented in Table 7.

From Table 7: Increasing STGCBs from 4 to 12 improves accuracy by 3.16%, as deeper networks capture richer hierarchical spatiotemporal dependencies. Beyond 12 blocks, accuracy drops slightly, indicating over-smoothing in deep graph convolution layers. Doubling depth from 4s to 8s increases FLOPs by 81.1% for a 2.33% accuracy gain. ASTM-Net- 12s achieves the optimal balance, delivering SOTA accuracy with moderate FLOPs. While this study focuses on high-end GPUs, future work will explore lightweight variants and hardware optimization (e.g., quantization) for edge devices. Addi­ tionally, automated neural architecture search could further refine depth and branch configurations for specific use cases.

E.  Statistical analysis with sota methods

To comprehensively validate the performance superiority of ASTM-Net, this section conducts systematic statistical com­ parisons between the proposed method and existing state-of-the-art (SOTA) approaches. All experiments are performed on the NTU-RGB + D dataset under the X-Sub benchmark, covering traditional graph convolutional networks (GCNNs), dynamic graph methods, attention-enhanced models, and hybrid architectures. The results are summarized in Table 8.

As can be seen from Table 8, ASTM-Net reduces parameters by 53.8% compared to hybrid architectures (e.g., Wu et al. [27]) and by 36.6% against Transformer variants (e.g., SkateFormer [29]). Compared to dynamic graph methods (e.g., DGCN-MPA [23]), ASTM-Net achieves a 3.16% accuracy gain with similar parameter counts, validating the efficiency of its parameter-shared 3A-Graph optimization. In addition, ASTM-Net requires only 43.7% of the FLOPs of Liu et al. [45] and

**Table 7.  Depth ablation results.**

| Table 7. Depth ablation results. |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| Model Variant | #STGCBs | X-Sub↑ | #Params/M↓ | #FLOPs/G↓ | RTX 4070 Ti FPS↑ |
| ASTM-Net-4s | 4 | 89.12 | 2.15 | 8.42 | 120 |
| ASTM-Net-8s | 8 | 91.45 | 3.88 | 15.27 | 85 |
| ASTM-Net-12s (Proposed) | 12 | 92.28 | 5.77 | 21.39 | 45 |
| ASTM-Net-16s | 16 | 91.87 | 7.64 | 28.53 | 32 |

**Table 8.  A Comprehensive Comparison Of Astm-Net With Sota Methods.**

<table>
  <tr><th colspan="3">Table 8. A Comprehensive Comparison Of Astm-Net With Sota Methods.</th></tr>
  <tr><td>Method</td><td>#Params/M ↓</td><td>#FLOPs/G ↓</td><td>X-Sub↑</td><td>p-value (vs. ASTM-Net)↓</td></tr>
  <tr><td>Sighencea et al. [19]</td><td>3.26</td><td>16.41</td><td>81.45</td><td>&lt; 0.001</td></tr>
  <tr><td>Liu et al. [45]</td><td>6.59</td><td>48.95</td><td>91.46</td><td>0.012</td></tr>
  <tr><td>DGCN-MPA [23]</td><td>5.20</td><td>37.80</td><td>89.12</td><td>&lt; 0.001</td></tr>
  <tr><td>HAM-HGNet [24]</td><td>7.80</td><td>45.20</td><td>89.87</td><td>&lt; 0.001</td></tr>
  <tr><td>KDS-GCN [26]</td><td>3.90</td><td>18.50</td><td>90.34</td><td>0.003</td></tr>
  <tr><td>CBAM-STGCN [25]</td><td>4.50</td><td>22.30</td><td>90.78</td><td>0.008</td></tr>
  <tr><td>Wu et al. [27]</td><td>12.50</td><td>65.00</td><td>88.25</td><td>&lt; 0.001</td></tr>
  <tr><td>SkateFormer [29]</td><td>9.10</td><td>52.70</td><td>91.05</td><td>0.021</td></tr>
  <tr><td>ASTM-Net-ALLs</td><td>5.77</td><td>21.39</td><td>92.28</td><td>–</td></tr>
</table>

<table>
  <tr><th>SkateFormer [29]</th><th>9.10</th><th>52.70</th><th>91.05</th><th>0.021</th></tr>
  <tr><td>ASTM-Net-ALLs</td><td>5.77</td><td>21.39</td><td>92.28</td><td>–</td></tr>
  <tr><td colspan="2">https://doi.org/10.1371/journal.pone.0324605.t008</td></tr>
  <tr><td colspan="5">significantly fewer operations than self-attention-based SkateFormer. Against lightweight knowledge-driven models (e.g., KDS-GCN [41]), ASTM-Net improves accuracy by 1.94% with a marginal 15.6% FLOPs increase, demonstrating balanced</td></tr>
  <tr><td>design.</td></tr>
  <tr><td colspan="5">To quantify whether the accuracy improvements of ASTM-Net are statistically significant, we perform paired T-tests against key competitors using 10 repeated runs on the NTU-RGB + D X-Sub benchmark. The null hypothesis (H0) states that the accuracy difference is statistically insignificant (i.e., p \ge 0.05). Results are shown in Table 9.</td></tr>
  <tr><td colspan="5">As can be seen from Table 9, All p-values are &lt; 0.05, confirming that ASTM-Net’s accuracy improvements are statisti­</td></tr>
  <tr><td colspan="5">cally significant. Additionally, Narrow confidence intervals (e.g., [0.35, 1.29] for Liu et al. [45]) indicate consistent perfor­</td></tr>
  <tr><td colspan="3">mance advantages across repeated experiments, ruling out random chance.</td></tr>
  <tr><td colspan="5">By synergistically optimizing dynamic 3A-Graphs and multi-branch temporal modeling, ASTM-Net achieves SOTA accuracy while maintaining lightweight computational profiles Statistical validation confirms that the proposed method effectively addresses the limitations of fixed graph topologies and isolated spatiotemporal processing in conventional</td></tr>
  <tr><td colspan="4">approaches, offering a robust and efficient solution for skeleton-based activity recognition.</td></tr>
  <tr><td>F. Robust analysis</td></tr>
  <tr><td colspan="5">This chapter analyzes the robustness of ASTM-Net under occluded or missing skeleton data from both theoretical mecha­ nisms and experimental validation, revealing the anti-interference capabilities of its dynamic graph optimization and multi-</td></tr>
  <tr><td>branch temporal modeling.</td></tr>
  <tr><td colspan="5">Specifically, When partial nodes are missing due to occlusion, the activity-related graph (C-Graph) in the 3A-Graph dynamically reconstructs potential correlations of missing nodes through cross-temporal node similarity inference. For instance, if the right-hand node is occluded, the C-Graph can infer its position using the motion patterns of the left-hand node (e.g., symmetry in “clapping” actions). The trainable graph (B-Graph) learns statistical dependencies between nodes during end-to-end training, implicitly encoding common occlusion patterns (e.g., hand occlusion by the torso). This ensures stable feature representation even with partial node missing during testing. Further, The dilated convolutional branches in TMGM (dilation = 1, 3) focus on local details and long-range dependencies, respectively. When nodes are missing in a single frame, the high-dilation branch leverages cross-frame information to fill the gaps (e.g., inferring hand</td></tr>
  <tr><td colspan="2">Table 9. Representative T-Test Results.</td></tr>
  <tr><td>Compared Method</td><td colspan="2">Mean Accuracy Difference (%)↑</td><td>95% Confidence Interval</td><td>p-value↓</td></tr>
  <tr><td>ASTM-Net vs. Liu et al. [45]</td><td>+0.82</td><td>[0.35, 1.29]</td><td>0.012</td></tr>
  <tr><td>ASTM-Net vs. SkateFormer [30]</td><td>+1.23</td><td>[0.61, 1.85]</td><td>0.021</td></tr>
  <tr><td>ASTM-Net vs. KDS-GCN [26]</td><td>+1.94</td><td>[1.12, 2.76]</td><td>0.003</td></tr>
</table>

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 21 / 30 positions from preceding 5 frames). The pooling branch in TMGM suppresses noisy nodes by selecting salient features via max-pooling, while the standalone 1  \times  1 convolutional branch preserves raw features to avoid over-reliance on cor­ rupted data.

In the simulation experiment, the following three occlusion strategies are carried out:

1)	Random Node Drop (RND): 30% of nodes are randomly masked (coordinates set to zero) per frame.

2)	Continuous Frame Occlusion (CFO): All hand nodes (IDs 8–12) are masked in 10 randomly selected frames.

3)	Noise Injection (NI): Gaussian noise (\sigma = 0.1) is added to 20% of node coordinates.

Robust comparison results with other SOTA methods are shown in Table 10. The accuracy results demonstrate ASTM-Net’s superior robustness:

1)	RND: ASTM-Net achieves 86.94% accuracy, outperforming Liu et al. [45], SkateFormer, and DGCN-MPA. This high­ lights the effectiveness of its dynamic 3A-Graph in reconstructing missing node correlations through cross-temporal activity patterns.

2)	CFO: ASTM-Net attains 82.17% accuracy, surpassing SkateFormer and HAM-HGNet, validating the multi-branch TMGM’s ability to leverage long-range dependencies for occlusion recovery.

3)	NI: ASTM-Net retains 89.05% accuracy with only a 3.23% drop from the original data, significantly lower than Sigh­ encea et al. [19] (5.61% drop) and KDS-GCN (3.39% drop), indicating robust noise suppression via attention-guided feature fusion.

Notably, ASTM-Net consistently outperforms hybrid architectures (e.g., Wu et al. [27]: 79.12% under RND) and attention-enhanced models (e.g., CBAM-STGCN: 83.45% under RND), proving that its dynamic graph optimization and multi-scale temporal modeling synergistically mitigate occlusion-induced feature degradation. The performance gap wid­ ens in extreme cases (e.g., CFO), where ASTM-Net’s accuracy exceeds Liu et al. [45] by 3.72%, emphasizing its adapt­ ability to real-world partial observation challenges.

G.  Generalization analysis

To validate ASTM-Net’s robustness in real-world environments, we conduct extensive experiments on the Toyota Smarth­ ome dataset, which captures unscripted daily activities of elderly subjects in home settings. In this experiment, skeleton sequences are resized to 64 frames and normalized to hip-centric coordinates. The results as show in Table 11.

**Table 10.  Robustness Test Results.**

| Table 10. Robustness Test Results. |  |  |  |  |
| --- | --- | --- | --- | --- |
| Method | Original↑ | RND↑ | CFO↑ | NI↑ |
| Sighencea et al. [19] | 81.45 | 72.13 | 65.28 | 75.84 |
| Liu et al. [45] | 91.46 | 83.27 | 78.45 | 86.12 |
| DGCN-MPA [25] | 89.12 | 80.55 | 75.33 | 84.20 |
| HAM-HGNet [24] | 89.87 | 81.09 | 76.88 | 85.41 |
| KDS-GCN [26] | 90.34 | 82.76 | 77.62 | 86.95 |
| CBAM-STGCN [25] | 90.78 | 83.45 | 78.90 | 87.32 |
| Wu et al. [27] | 88.25 | 79.12 | 73.54 | 83.67 |
| SkateFormer [28] | 91.05 | 84.56 | 79.88 | 87.30 |
| ASTM-Net-ALLs | 92.28 | 86.94 | 82.17 | 89.05 |

NI↑

75.84

86.12

84.20

85.41

86.95

87.32

83.67

87.30

### 89.05 https://doi.org/10.1371/journal.pone.0324605.t011

**Table 11.  Generalization Test Results.**

<table>
  <tr><th colspan="2">Table 11. Generalization Test Results.</th></tr>
  <tr><td>Method</td><td>CS↑</td><td>CV1↑</td><td>CV2↑</td></tr>
  <tr><td>HAM-HGNet [24]</td><td>68.32</td><td>72.15</td><td>70.88</td></tr>
  <tr><td>KDS-GCN [26]</td><td>75.28</td><td>78.44</td><td>76.92</td></tr>
  <tr><td>CBAM-STGCN [25]</td><td>73.89</td><td>76.12</td><td>74.55</td></tr>
  <tr><td>Wu et al. [27]</td><td>76.55</td><td>79.01</td><td>77.33</td></tr>
  <tr><td>SkateFormer [29]</td><td>77.12</td><td>79.85</td><td>78.20</td></tr>
  <tr><td>ASTM-Net-ALLs</td><td>79.34</td><td>82.17</td><td>80.45</td></tr>
</table>

As shown, ASTM-Net achieves 79.34% on CS and 82.17% on CV1, surpassing Wu et al. [27] by 2.79% and 3.16%, respectively. This validates its ability to handle occlusions (e.g., hands behind objects) and viewpoint shifts through dynamic 3A-Graphs. In CV2, ASTM-Net attains 80.45%, outperforming SkateFormer [29] by 2.25%, demonstrating robust­ ness to mixed-view training and front-view testing. However, we found some failure cases, e.g., activities like “handing objects” achieve only 71.3% accuracy due to limited inter-person relationship modeling. sequential occlusion of critical joints (e.g., hip nodes) in long-duration activities (“clean dishes”) leads to ~8% accuracy drop. This is also our future direc­ tion of improvement.

H.  Visualizations

Taking the activity “jumping” as an example, Fig 8 illustrates the skeletal adjacency graph matrices without the optimi­ zation of the activity-related graph C_{k}, represented by the sum of the initialized matrix A_{k} and the trainable matrix B_{k} for the three spatial subsets (k = 1,2,3). Figs 8a-8c visualize A_{1} + B_{1}, A_{2} + B_{2}, and A_{3} + B_{3}, respectively. In the visualization, darker color blocks indicate stronger node affinities, while lighter colors represent weaker relationships.

The results show that:

1)	In the first spatial subset, the learned adjacency graph focuses more on self-connections (indicated by the concentra­ tion of dark blocks along the diagonal). In the second and third spatial subsets, the topology focuses on the affinities between different nodes.

2)	The learned adjacency graph can capture non-physical node affinities.

3)	The adjacency graphs differ across the three spatial subsets, providing rich features for spatial graph convolution.

Fig 9 further visualizes the activity-related graphs C_{ki} at different time periods within the same spatial subset, still using the “jumping” activity as an example. As described in the methodology section, C_{k} is obtained by concatenating s https://doi.org/10.1371/journal.pone.0324605.g009

![Fig 8.  The visualizations of skeletal adjacency graph matrices without the activity-related graph.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p23_1.png)

*Fig 8.  The visualizations of skeletal adjacency graph matrices without the activity-related graph.*

![Fig 9.  The visualizations of the activity-related graphs.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p24_1.png)

*Fig 9.  The visualizations of the activity-related graphs.*

activity-related graphs, with s = 4 as determined in last section. In Fig 9, C_{ki}  \in  R^{N}∗N, i = 1, 2, 3, 4 represents the activity-­ related graph at different time periods. Figs 9a-9d show the visualization results for C_{k}_{1}, C_{k}_{2}, C_{k}_{3}, and C_{k}_{4}, respectively.

The results demonstrate:

1)	The activity-related graphs differ from the unoptimized graph, enriching the spatiotemporal features of the nodes.

2)	Activity-related graphs vary across different time periods, verifying the necessity of optimizing node affinities dynami­ cally over time.

Fig 10 visualizes the final learned skeletal adjacency graphs G_{ki}, i = 1, 2, 3, 4 for different activities at different time periods. All graphs are derived from the same convolutional layer and spatial subset of ASTM-Net. Specifically, each circle represents a node, with its size indicating the connection strength between the current node and the 25th node (the hand node). Only the top 5 strongest connections are visualized.

The results show:

These findings validate our hypothesis: different samples with distinct activity patterns require different adjacency graphs to capture node affinities, and optimizing skeletal graphs with activity-related graphs over time is necessary.

![Fig 10.  The 3A-Graph3A-graph visualizations with different settings.](assets/Lightweight_and_efficient_skeleton-based_sports_activity_recogni/fig_p25_1.png)

*Fig 10.  The 3A-Graph3A-graph visualizations with different settings.*

https://doi.org/10.1371/journal.pone.0324605.g010

## V.  Discussion

a.  Novel added value

Beyond advancing state-of-the-art accuracy, ASTM-Net introduces two paradigm-shifting values that redefine efficiency and adaptability in skeleton-based HAR:

1  ) Dynamic 3A-Graphs with Activity-Conditioned Optimization.  Prior works either use fixed physical graphs [19] or learn global attention weights [25], neglecting the temporal dependency of node relationships. Our 3A-Graph framework innovates by:

a)	 Decomposing graph learning into stable (physical/trainable graphs) and dynamic (activity-related graph) components;

b)	Conditioning spatial connections on localized temporal features through segment-wise similarity learning (i.e., (8));

c)	 Optimizing graphs via parameter-shared inference across time segments (s = 4), reducing parameters versus

layer-specific alternatives [23].

2)  Parameter-Efficient Multi-Branch Temporal Modeling.  TMGM redefines temporal convolution through heterogeneous branches that collaboratively capture:

a)	Short-range dynamics (d=1 branch: 5-frame micro-motions);

b)	Long-range dependencies (d=3 branch: 13-frame macro-trends);

c)	 Noise resilience (pooling branch: suppressing transient outliers);

d)	Feature preservation (1*1 branch: maintaining raw signal fidelity);

Unlike transformer-based methods [29] that compute O(T2) attention weights, TMGM’s branched convolutions operate at O(T) complexity, achieving lower FLOPs than MST-GCN [54] while improving accuracy (as shown in Table 3).

b.  Future work

This section evaluates the performance of ASTM-Net under different hyper-parameter settings, including the reduction ratio r and the number of feature segments s (i.e., the number of time periods). The results are presented in Table 6.

While ASTM-Net achieves state-of-the-art performance in skeleton-based activity recognition, several promising direc­ tions remain to furtherenhance its applicability and scalability in real-world scenarios. Below, we discuss potential exten­ sions and improvements:

1)  Integration with Transformer Architectures.  The success of Transformers in modeling long-range dependencies suggests opportunities to enhance ASTM-Net’s temporal modeling capabilities. Replacing TMGM’s dilated convolutions with lightweight self-attention mechanisms could better capture global temporal patterns (e.g., periodic motions in “jumping rope”). Combining ASGM’s dynamic graphs with Transformer encoders may further exploit local-global spatiotemporal dependencies. To validate this, future work could compare the original ASTM- Net with transformer-enhanced variants such as ASTM-Transformer (replacing TMGM with vanilla multi-head selfattention) and ASTM-EfficientFormer (hybrid sparse attention + dilated convolution) on NTU-RGB + D and Toyota Smarthome datasets. Key metrics would include accuracy, FLOPs, and inference speed on edge devices like NVIDIA Jetson. Implementation steps could integrate shifted window attention to reduce quadratic complexity and apply dynamic token sparsification to prune non-salient frames. Quantizing attention weights to INT8 would further optimize edge deployment. Evaluation would focus on accuracy-FLOPs trade-offs and interpreting attention maps for critical motion phases. Challenges such as computational overhead could be mitigated via low-rank approximations or hardware-aware optimizations.

2)  Self-Supervised Learning for Label Efficiency.  Current methods rely on fully annotated datasets, limiting scalability. Self-supervised pretraining via masked joint reconstruction or contrastive learning could improve label efficiency and robustness. For instance, pretraining on PKU-MMD V2 (5.4M unlabeled frames) with strategies like masking 40% of joints/frames (L1 reconstruction loss) or generating positive pairs via temporal cropping/jittering could enable robust feature learning. Downstream fine-tuning on NTU-RGB + D (10%/30%/100% labeled data) and Toyota Smarthome would validate label efficiency gains. Success metrics would include achieving >85% accuracy with 10% labels (vs. 70% supervised baseline) and improved robustness to occlusions (RND/CFO metrics). Visualization of pretrained embeddings via t-SNE could verify activity clustering. Cross-modal alignment with CLIP embeddings, if RGB data is available, might further enhance generalization to unseen domains like medical rehabilitation.

architecture for varying computational capacities (e.g., smartphones vs. IoT sensors) in FL frameworks could further enhance its adaptability.

4)  Multi-modal fusion for complex scenarios.  While ASTM-Net focuses on skeleton data, integrating complementary modalities could address its limitations in occlusion-heavy environments. RGB-skeleton fusion using attention-based modules could combine skeletal features with RGB appearance cues to improve performance in scenarios like object interactions (e.g., “open fridge”). Depth maps can refine node distances in the 3A-Graph, improving robustness to viewpoint changes. Additionally, for activities with sound cues, such as “clapping” or “typing,” synchronizing audio features with skeletal motions via cross-modal transformers could enhance recognition.

5)  Edge deployment and hardware optimization.  To realize real-time HAR on resource-constrained devices, future work should explore quantization and pruning techniques. Post-training quantization could reduce ASTM-Net’s precision (FP32  \to  INT8), while pruning redundant graph connections would help to decrease model size and improve inference speed. Hardware-aware neural architecture search (NAS) could be employed to automatically design ASTM-Net variants optimized for specific hardware chips like NVIDIA Jetson or ARM CPUs. Furthermore, enabling incremental learning on edge devices could allow for adaptation to user-specific motion patterns without requiring cloud dependency.

6  ) Real-world deployment and industrial validation.  Although ASTM-Net achieves promising performance on benchmark datasets such as Toyota Smarthome, its practical deployment in real-world scenarios—especially in embedded systems like wearable devices and smart surveillance systems—remains a critical next step. For wearable device integration, hardware-specific optimization is necessary to adapt ASTM-Net to ultra-low-power ARM processors (e.g., Cortex-M7), involving pruning redundant graph connections and employing INT8 quantization for reduced power consumption. Comprehensive energy efficiency evaluations using commercial wearables such as Fitbit Sense and Apple Watch under continuous activity monitoring conditions would further ensure practical viability. Additionally, enabling on-device fine-tuning could facilitate personalized models capable of adapting to individual-specific motion patterns, particularly beneficial in medical scenarios like detecting gait abnormalities in Parkinson’s patients. For smart surveillance applications, ASTM-Net can be enhanced by incorporating multi-camera fusion strategies to robustly handle occlusions in crowded environments, leveraging synchronized skeleton streams from distributed camera systems. An edge-cloud hybrid deployment—deploying lightweight ASGM modules at edge devices for instantaneous alerts such as fall detection, while conducting deeper multi-scale TMGM analyses on cloud platforms—could balance responsiveness with computational efficiency. Moreover, adopting federated learning methodologies would enable privacy-preserving inference, anonymizing sensitive skeletal data across distributed surveillance nodes to ensure compliance with GDPR and CCPA regulations. Finally, establishing industrial partnerships, such as collaborations with healthcare providers like Philips Lifeline to validate the system’s reliability in elderly monitoring or integration with smart home manufacturers such as Bosch or Nest for realtime IoT activity recognition, would significantly facilitate the practical adoption and validation of ASTM-Net in real-world applications.

## VI.  Conclusion

This paper introduced ASTM-Net, a novel framework for skelecton-based activity recognition that integrates spatial and temporal information through the proposed ASGM and TMGM modules. By dynamically modeling 3A-Graphs, ASGM effectively captures the temporal variations in node affinities and enhances the robustness of spatial graph convolu­ tions. The incorporation of TMGM further strengthens the temporal modeling capacity by extracting multi-scale features. Experimental results on different datasets highlight the superior performance and efficiency of ASTM-Net, achieving state-of-the-art accuracy with significantly reduced parameters and computational costs compared to existing methods. Ablation studies validate the contributions of ASGM and 3A-Graphs to the overall performance. In conclusion, ASTM-Net provides a lightweight yet powerful solution for skeleton-based activity recognition, paving the way for future research into dynamic graph modeling for HAR. In addition, while evaluated on general daily activities, the proposed ASTM-Net can be potentially applied to sports scenarios (e.g., analysing athlete movements) due to its capability in modelling dynamic joint correlations. Future work includes validating ASTM-Net on sports-specific datasets (e.g., basketball tactical analysis) to further explore its robustness in high-dynamic scenarios.

## Author contributions

## Conceptualization: Ning Zhang.

## Data curation: Ying Jia, GuoJin Zhao.

## Funding acquisition: Ning Zhang.

## Investigation: XiuPing Wang.

## Methodology: Bin Wu, Mei Xue, GuoJin Zhao, XiuPing Wang, Chunlei Zhang.

## Project administration: Ning Zhang.

## Software: Ying Jia, XiuPing Wang, Chunlei Zhang.

## Writing – original draft: Bin Wu.

## Writing – review & editing: Ying Jia.

## References

1. Kaur H, Rani V, Kumar M. Human activity recognition: A comprehensive review. Expert Systems. 2024;41(11). https://doi.org/10.1111/exsy.13680

2. Karim M, Khalid S, Aleryani A. Human action recognition systems: A review of the trends and state-of-the-art. IEEE Access. 2024.

3. Nir O, Vidra I, Neeman A. VCR: Video representation for contextual retrieval. In: Proceedings of the International Conference on Computing, Machine Learning and Data Science; 2024. 1–9.

4. Putawa RA. Exploring User Experience and Immersion Levels in Virtual Reality: A Comprehensive Analysis of Factors and Trends. Int J Res Metav. 2024;1(1):20–39. https://doi.org/10.47738/ijrm.v1i1.3

5. Zhang J, Li Y. SL-GCNN: A Graph Convolutional Neural Network for Granular Human Motion Recognition. IEEE Access. 2024.

## 6. Pei C. DMA-SGCN for video motion recognition: A tool for advanced sports analysis. IEEE Access. 2024.

7. Sain MK, Laskar R, Singha J, Saini S. Patient activity recognition for robust performance under varied illumination and cluttered background in indoor environment. International Journal of Computers and Applications. 2024;46(12):1219–45. https://doi.org/10.1080/1206212x.2024.2427287

8. Lalapura VS, Bhimavarapu VR, Amudha J, Satheesh HS. A Systematic Evaluation of Recurrent Neural Network Models for Edge Intelligence and Human Activity Recognition Applications. Algorithms. 2024;17(3):104. https://doi.org/10.3390/a17030104

9. Sharen H, Jani Anbarasi L, Rukmani P, Gandomi AH, Neeraja R, Narendra M. WISNet: A deep neural network based human activity recognition system. Expert Systems with Applications. 2024;258:124999. https://doi.org/10.1016/j.eswa.2024.124999

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 28 / 30

Sighencea BI, Stanciu IR, Căleanu CD. D-STGCN: Dynamic Pedestrian Trajectory Prediction Using Spatio-Temporal Graph Convolutional Net­ 19. works. J Electronics. 2023;12(3):611.

20. Zhang J, Sun MT. From ChebNet to ChebGibbsNet. arXiv preprint. 2024. https://doi.org/arXiv:2412.01789

21. Ai G, Pang G, Qiao H, et al. GrokFormer: Graph Fourier Kolmogorov-Arnold Transformers J. arXiv preprint arXiv:2411.17296. 2024.

22. Mukta FT. Advanced Mathematical Graph-based Machine Learning and Deep Learning Models for Drug Design. University of Kentucky. 2024.

23. Yang H, Wang S, Lu J. Hierarchical adaptive multi-scale hypergraph attention convolution network for skeleton-based action recognition. J Applied Soft Computing. 2025:112855.

24. Qin J, Zhang S, Wang Y, Yang F, Zhong X, Lu W. Improved skeleton-based activity recognition using convolutional block attention module. Com­ puters and Electrical Engineering. 2024;116:109231. https://doi.org/10.1016/j.compeleceng.2024.109231

25. Roy A, Tiwari A, Saurav S, Singh S. Enhancing skeleton-based action recognition using a knowledge-driven shift graph convolutional network. Computers and Electrical Engineering. 2024;120:109633. https://doi.org/10.1016/j.compeleceng.2024.109633

26. Huang S, Chen PY, McCann JA. DiffAR: Adaptive Conditional Diffusion Model for Temporal-augmented Human Activity Recognition. IJCAI. 2023:3812–20.

27. Wu J, Liu Q. A Novel Spatio-Temporal Network of Multi-channel CNN and GCN for Human Activity Recognition Based on BAN. Neural Process Lett. 2023;55(8):11489–507. https://doi.org/10.1007/s11063-023-11385-z

28. Mansouri A, Elzaar A, Madani M, Bakir T. Design and Hardware Implementation of CNN-GCN Model for Skeleton-Based Human Action Recogni­ tion. Wseas Transactions on Computer Research. 2024;12:318–27. https://doi.org/10.37394/232018.2024.12.31

29. Do J, Kim M. Skateformer: skeletal-temporal transformer for human action recognition. In: European Conference on Computer Vision; 2024. 401–20.

30. Li Z, Li Y, Gao Z. Spatiotemporal Representation Learning for Video Anomaly Detection. IEEE Access. 2020;8:25531–42. https://doi.org/10.1109/ access.2020.2970497

Hożyń S. Advancements in Visual Gesture Recognition for Underwater Human-Robot Interaction: A Comprehensive Review J. IEEE Access. 2024. 31.

32. Younsi M, Yesli S, Diaf M. Depth-based human action recognition using histogram of templates. Multimed Tools Appl. 2023;83(14):40415–49. https://doi.org/10.1007/s11042-023-16989-0

33. Wang Y, Han Y, Wang C. Computation-efficient deep learning for computer vision: A survey. J Cybernetics and Intelligence. 2024.

34. Cheng Y, Bai Y, Yang J, Tan X, Xu T, Cheng R. Analysis and prediction of infectious diseases based on spatial visualization and machine learning. Sci Rep. 2024;14(1):28659. https://doi.org/10.1038/s41598-024-80058-1 PMID: 39562802

35. Li D, Lu C, Chen Z, et al. Graph Neural Networks in Point Clouds: A Survey. J Remote Sensing. 2024;16(14):2518.

36. Xu L, Chen J, Han Z, Zhang Y. TaylorNet: A novel approach for spectral filter learning on graph data. Neurocomputing. 2024;605:128358. https:// doi.org/10.1016/j.neucom.2024.128358

37. Mathivanan JS, Dhayabaran VV, David MR, Karuna Nidhi MB, Prasath KM, Suvaithenamudhan S. Application of Deep Learning Neural Networks in Computer-Aided Drug Discovery: A Review. CBIO. 2024;19(9):851–8. https://doi.org/10.2174/0115748936276510231123121404

38. Yang Y, Hossain MZ, Stone E, Rahman S. Spatial transcriptomics analysis of gene expression prediction using exemplar guided graph neural network. Pattern Recognition. 2024;145:109966. https://doi.org/10.1016/j.patcog.2023.109966

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 29 / 30

48. Das S, Dai R, Koperski M, et al. Toyota smarthome: Real-world activities of daily livingC. Proceedings of the IEEE/CVF international conference on computer vision; 2019. p. 833–42.

49. Keçeli AS, Kaya A, Can AB. Combining 2D and 3D deep models for action recognition with depth information. SIViP. 2018;12(6):1197–205. https:// doi.org/10.1007/s11760-018-1271-3

50. Jang S, Lee H, Kim WJ. Multi-scale Structural Graph Convolutional Network for Skeleton-based Action Recognition. IEEE Transactions on Circuits and Systems for Video Technology. 2024.

51. Huang P, Jiang H, Wang S. Enhancing human behavior recognition with dynamic graph convolutional networks and multi-scale position attention. International Journal of Intelligent Computing and Cybernetics. 2024.

52. Chen H, Jiang Y, Ko H. Pose-Guided Graph Convolutional Networks for Skeleton-Based Action Recognition. IEEE Access. 2022;10:111725–31. https://doi.org/10.1109/access.2022.3214812

53. Zhu X, Zhu Y, Wang H, Wen H, Yan Y, Liu P. Skeleton Sequence and RGB Frame Based Multi-Modality Feature Fusion Network for Action Recog­ nition. ACM Trans Multimedia Comput Commun Appl. 2022;18(3):1–24. https://doi.org/10.1145/3491228

54. Wu J, Wang L, Chong G. 2S-AGCN human behavior recognition based on new partition strategy. In: 2022 Asia-Pacific Signal and Information Processing Association Annual Summit and Conference (APSIPA ASC); 2022. 157–63.

55. Zhou J, Liu Z, Tan M. Recommendations for Inactive Users: A Cross Domain Approach with Graph Neural Networks. International Journal of Machine Learning and Cybernetics. 2024:1–15.

56. Singh A, Van De Ven P, Eising C. Dynamic filter application in graph convolutional networks for enhanced spectral feature analysis and class dis­ crimination in medical imaging. IEEE Access. 2024.

PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 30 / 30

## Footnotes
- **[p.2.1]** Funding: The author(s) received no specific funding for this work.
- **[p.2.2]** Competing interests: The authors have declared that no competing interests exist.
- **[p.2.3]** 1)	These methods neglect the dynamic changes in adjacency graph induced by node movements, failing to fully exploit activity information;
- **[p.2.4]** 2)	They overlook the mutualities between spatial and temporal information, which are critical for accurately recognizing skeletal activities.
- **[p.2.5]** 1)	Linkages between moving nodes: Nodes from the same body part exhibit synchro­ nized movements due to inherent physical connections (e.g., nodes in the right
- **[p.2.6]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 2 / 30
- **[p.3.7]** 4)	The proposed ASTM-Net achieves state-of-the-art performance with significantly fewer parameters and lower compu­ tational costs compared to existing methods, making it a lightweight and efficient solution for skelecton-based activity recognition.
- **[p.3.8]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 3 / 30
- **[p.4.9]** https://doi.org/10.1371/journal.pone.0324605.t001
- **[p.5.10]** https://doi.org/10.1371/journal.pone.0324605.g001
- **[p.5.11]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 5 / 30
- **[p.6.12]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 6 / 30
- **[p.7.13]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 7 / 30
- **[p.8.14]** https://doi.org/10.1371/journal.pone.0324605.g002
- **[p.9.15]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 9 / 30
- **[p.10.16]** https://doi.org/10.1371/journal.pone.0324605.g004
- **[p.10.17]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 10 / 30
- **[p.11.18]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 11 / 30
- **[p.12.19]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 12 / 30
- **[p.13.20]** https://doi.org/10.1371/journal.pone.0324605.g005
- **[p.14.21]** https://doi.org/10.1371/journal.pone.0324605.g007
- **[p.15.22]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 15 / 30
- **[p.16.23]** 2)	X-Set: Samples with even setup IDs (54,468 samples) form the training set, including 10% (5,447 samples) for valida­ tion, while odd-ID samples (58,486 samples) are used for testing.
- **[p.16.24]** 1)	Cross-Subject (CS): Train on 11 subjects (11,550 samples), test on 7 subjects (2,200 samples).
- **[p.16.25]** 2)	Cross-View (CV1 & CV2):
- **[p.16.26]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 16 / 30
- **[p.17.27]** 3)	Skelecton-Only Performance: While Zhu et al. [55] incorporates multi-modal features (i.e., RGB and skelecton trajecto­ ries), our method, using only skelecton trajectories, still achieves higher recognition accuracy.
- **[p.17.28]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 17 / 30
- **[p.19.29]** https://doi.org/10.1371/journal.pone.0324605.t005
- **[p.19.30]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 19 / 30
- **[p.20.31]** https://doi.org/10.1371/journal.pone.0324605.t007
- **[p.20.32]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 20 / 30
- **[p.21.33]** https://doi.org/10.1371/journal.pone.0324605.t009
- **[p.22.34]** https://doi.org/10.1371/journal.pone.0324605.t010
- **[p.22.35]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 22 / 30
- **[p.23.36]** https://doi.org/10.1371/journal.pone.0324605.g008
- **[p.23.37]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 23 / 30
- **[p.24.38]** 1)	For both coarse activities (e.g., “sitting,” “clapping,” “waving”) and fine-grained activities (e.g., “writing,” “using a phone/ tablet,” “sneezing/coughing”), the learned skeletal adjacency graphs differ across time periods.
- **[p.24.39]** 2)	For different activities with highly similar activity trajectories (e.g., “writing” and “using a phone/tablet”), the learned adjacency graphs are still distinguishable.
- **[p.24.40]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 24 / 30
- **[p.25.41]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 25 / 30
- **[p.26.42]** 3)  Privacy-preserving HAR via federated learning.  For sensitive applications like healthcare or smart homes, federated learning (FL) can enable collaborative model training without sharing raw skeleton data. One promising direction is extending ASGM to learn personalized 3A-Graphs on distributed devices while aggregating only graph parameters, avoiding the need to transmit raw data. Another avenue is injecting noise into graph updates during FL to prevent inference attacks on user-specific motion patterns, thus ensuring privacy. Furthermore, optimizing ASTM-Net’s
- **[p.26.43]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 26 / 30
- **[p.27.44]** PLOS One | https://doi.org/10.1371/journal.pone.0324605  July 8, 2025 27 / 30
- **[p.28.45]** 10. Yang J, Liao T, Zhao J, Yan Y, Huang Y, Zhao Z, et al. Domain Adaptation for Sensor-Based Human Activity Recognition with a Graph Convolu­ tional Network. Mathematics. 2024;12(4):556. https://doi.org/10.3390/math12040556
- **[p.28.46]** 11. Shin Y, Yoon Y. PGCN: Progressive graph convolutional networks for spatial–temporal traffic forecasting. IEEE Transactions on Intelligent Trans­ portation Systems. 2024.
- **[p.28.47]** 12. Li Q, Xu P, Yang X. Spatial–Temporal Traffic Prediction With an Interactive Spatial-Enhanced Graph Convolutional Network Model. IEEE Transac­ tions on Intelligent Transportation Systems. 2024.
- **[p.28.48]** 13. Wang L, Huang Y, Wu H. Spatial-temporal Graph Convolutional Networks with Diversified Transformation for Dynamic Graph Representation Learning. arXiv preprint. 2024. https://doi.org/arXiv:2408.02704
- **[p.28.49]** 14. zhang X, Chen X, Tang H, Wu Y, Shen H, Li J. AdpSTGCN: Adaptive spatial–temporal graph convolutional network for traffic forecasting. Knowledge-Based Systems. 2024;301:112295. https://doi.org/10.1016/j.knosys.2024.112295
- **[p.28.50]** 15. Li B, He M, Dai Y, Cheng X, Chen Y. 3D skeleton based action recognition by video-domain translation-scale invariant mapping and multi-scale dilated CNN. Multimed Tools Appl. 2018;77(17):22901–21. https://doi.org/10.1007/s11042-018-5642-0
- **[p.28.51]** 16. Xie Y, Xiang J, Li X. An overview of behavioral recognition. J Information Technology and Control. 2024;53(2):619–52.
- **[p.28.52]** 17. Kaseris M, Kostavelis I, Malassiotis S. A Comprehensive Survey on Deep Learning Methods in Human Activity Recognition. MAKE. 2024;6(2):842– 76. https://doi.org/10.3390/make6020040
- **[p.28.53]** 18. Feng Y, Zhao Y, Zhang X, et al. Predicting spatio-temporal traffic flow: a comprehensive end-to-end approach from surveillance cameras J. Trans­ portmetrica B: Transport Dynamics, 2024, 12(1):2380915.
- **[p.29.54]** 39. Zou H, Chen Z, Zhang J. GT-WHAR: A Generic Graph-Based Temporal Framework for Wearable Human Activity Recognition With Multiple Sen­ sors. IEEE Transactions on Emerging Topics in Computational Intelligence. 2024.
- **[p.29.55]** 40. Islam MM, Iqbal T. Multi-GAT: A Graphical Attention-Based Hierarchical Multimodal Representation Learning Approach for Human Activity Recogni­ tion. IEEE Robot Autom Lett. 2021;6(2):1729–36. https://doi.org/10.1109/lra.2021.3059624
- **[p.29.56]** 41. Zhang P, Lan C, Zeng W. Semantics-guided neural networks for efficient skeleton-based human action recognition. In: Proceedings of the IEEE/ CVF Conference on Computer Vision and Pattern Recognition; 2020. 1112–21.
- **[p.29.57]** 42. Su N, Chen X, Guan J, Wang X, Zhou L, Wang J, et al. Radar Multi-Feature Graph Representation and Graph Network Fusion Target Detection Methods. Chinese Journal of Information Fusion. 2025;2(1):59–69. https://doi.org/10.62762/cjif.2025.413277
- **[p.29.58]** 43. Zhang W, Hong Q. Modeling Brain Functional Networks Using Graph Neural Networks: A Review and Clinical Application. IECE Transactions on Intelligent Systematics. 2024;1(2):58–68. https://doi.org/10.62762/tis.2024.680959
- **[p.29.59]** 44. Wang K, Ye C, Zhang H, et al. Graph-Driven Multimodal Feature Learning Framework for Apparent Personality Assessment J. arXiv preprint arXiv:2504.11515. 2025. https://doi.org/10.48550/arXiv.2504.11515
- **[p.29.60]** 45. Lin KY, Zhou J, Zheng WS. Human-centric transformer for domain adaptive action recognition. IEEE Transactions on Pattern Analysis and Machine Intelligence. 2024.
- **[p.29.61]** 46. Liu Y, Li Y, Zhang H, Zhang X, Xu D. Decoupled Knowledge Embedded Graph Convolutional Network for Skeleton-Based Human Action Recogni­ tion. IEEE Trans Circuits Syst Video Technol. 2024;34(10):9445–57. https://doi.org/10.1109/tcsvt.2024.3399126
- **[p.29.62]** 47. Jiang Y, Deng H. Lighter and faster: A multi-scale adaptive graph convolutional network for skeleton-based action recognition. Engineering Applica­ tions of Artificial Intelligence. 2024;132:107957. https://doi.org/10.1016/j.engappai.2024.107957