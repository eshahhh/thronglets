import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react'

function Section({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  return (
    <div className="docs-section">
      <h2 
        className="docs-section-title" 
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        {title}
      </h2>
      {isOpen && <div className="docs-section-content">{children}</div>}
    </div>
  )
}

function DocsPage() {
  return (
    <div className="docs-page">
      <div className="docs-container">
        <div className="docs-header">
          <h1>Thronglets Documentation</h1>
          <Link to="/" className="btn btn-secondary">
            <ArrowLeft size={16} />
            Back to Simulation
          </Link>
        </div>
        
        <div className="docs-content">
          <Section title="Overview" defaultOpen={true}>
            <p>
              Thronglets is an emergent economics simulation where autonomous agents interact 
              in a resource-limited environment. The simulation explores how economic behaviors, 
              social structures, and institutions emerge naturally through agent interactions 
              without predefined rules about markets or currencies.
            </p>
            <p>
              Each agent is powered by a Large Language Model (LLM) that makes decisions based 
              on the agent's current state, needs, inventory, and observations about the world. 
              Agents must gather resources, trade with others, and form social connections to 
              survive and thrive.
            </p>
            <h3>Key Research Questions</h3>
            <ul>
              <li>Will agents naturally develop currency or medium of exchange?</li>
              <li>How do trading networks and market structures emerge?</li>
              <li>What specialization patterns develop over time?</li>
              <li>How do social institutions (guilds, cooperatives) form?</li>
              <li>How does wealth distribution evolve?</li>
              <li>What governance mechanisms emerge?</li>
            </ul>
          </Section>

          <Section title="World Structure">
            <h3>Locations</h3>
            <p>
              The world consists of interconnected locations, each with different resource 
              availability and characteristics. Agents can only interact with other agents 
              at the same location.
            </p>
            
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Type</th>
                  <th>Primary Resources</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Northern Forest</td>
                  <td>Forest</td>
                  <td>Wood, Berries, Herbs</td>
                  <td>Higher danger level</td>
                </tr>
                <tr>
                  <td>Southern Forest</td>
                  <td>Forest</td>
                  <td>Wood, Berries, Mushrooms</td>
                  <td>Lower danger, more berries</td>
                </tr>
                <tr>
                  <td>Central Plains</td>
                  <td>Plains</td>
                  <td>Grain, Hay, Clay</td>
                  <td>Easy access, primary farming area</td>
                </tr>
                <tr>
                  <td>Village Square</td>
                  <td>Settlement</td>
                  <td>Water</td>
                  <td>Trading hub, safest location, best shelter</td>
                </tr>
                <tr>
                  <td>River Crossing</td>
                  <td>River</td>
                  <td>Fish, Water, Clay</td>
                  <td>Abundant fish, higher danger</td>
                </tr>
                <tr>
                  <td>Mountain Base</td>
                  <td>Mountain</td>
                  <td>Stone, Ore, Gems</td>
                  <td>Valuable minerals, difficult access</td>
                </tr>
                <tr>
                  <td>Deep Caves</td>
                  <td>Cave</td>
                  <td>Ore, Gems, Stone</td>
                  <td>Highest danger, rarest resources</td>
                </tr>
                <tr>
                  <td>Coastal Shore</td>
                  <td>Coast</td>
                  <td>Fish, Salt, Shells</td>
                  <td>Salt for preservation, shells for crafting</td>
                </tr>
              </tbody>
            </table>

            <h3>Movement</h3>
            <p>
              Agents can only move to adjacent locations. Each edge between locations has:
            </p>
            <ul>
              <li><strong>Distance:</strong> Base travel cost (1.0 - 4.0)</li>
              <li><strong>Difficulty:</strong> Multiplier for travel cost (0.5 - 2.5)</li>
            </ul>
            <p>
              Travel cost = Distance × Difficulty × Destination Access Cost
            </p>
          </Section>

          <Section title="Resources">
            <h3>Resource Categories</h3>
            
            <h4>Raw Materials</h4>
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Base Value</th>
                  <th>Stack Size</th>
                  <th>Decay Rate</th>
                  <th>Found At</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>Wood</td><td>2</td><td>50</td><td>0%</td><td>Forests</td></tr>
                <tr><td>Stone</td><td>3</td><td>30</td><td>0%</td><td>Mountains, Caves</td></tr>
                <tr><td>Iron Ore</td><td>8</td><td>20</td><td>0%</td><td>Mountains, Caves</td></tr>
                <tr><td>Clay</td><td>2</td><td>40</td><td>0%</td><td>Plains, River</td></tr>
                <tr><td>Hay</td><td>1</td><td>60</td><td>1%</td><td>Plains</td></tr>
              </tbody>
            </table>

            <h4>Food Items</h4>
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Base Value</th>
                  <th>Food Value</th>
                  <th>Decay Rate</th>
                  <th>Found At</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>Fish</td><td>5</td><td>25</td><td>10%</td><td>River, Coast</td></tr>
                <tr><td>Berries</td><td>2</td><td>10</td><td>15%</td><td>Forests</td></tr>
                <tr><td>Grain</td><td>3</td><td>15</td><td>2%</td><td>Plains</td></tr>
                <tr><td>Mushrooms</td><td>4</td><td>12</td><td>20%</td><td>Southern Forest</td></tr>
              </tbody>
            </table>

            <h4>Valuables & Special</h4>
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Base Value</th>
                  <th>Rarity</th>
                  <th>Use</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>Gems</td><td>50</td><td>Very Rare</td><td>Jewelry crafting, potential currency</td></tr>
                <tr><td>Salt</td><td>6</td><td>Uncommon</td><td>Food preservation</td></tr>
                <tr><td>Herbs</td><td>4</td><td>Moderate</td><td>Medicine crafting</td></tr>
                <tr><td>Shells</td><td>3</td><td>Common</td><td>Decorative crafting</td></tr>
              </tbody>
            </table>

            <h3>Resource Regeneration</h3>
            <p>
              Resources regenerate over time at each location up to a maximum cap:
            </p>
            <ul>
              <li><strong>Fast regeneration:</strong> Water (50/tick), Fish (10/tick), Berries (8/tick)</li>
              <li><strong>Medium regeneration:</strong> Wood (5/tick), Hay (5/tick), Mushrooms (6/tick)</li>
              <li><strong>Slow regeneration:</strong> Stone (1/tick), Ore (0.5/tick), Gems (0.1/tick)</li>
            </ul>

            <h3>Resource Decay</h3>
            <p>
              Perishable items in agent inventory decay each tick:
            </p>
            <ul>
              <li>Mushrooms: 20% decay rate (highest)</li>
              <li>Berries: 15% decay rate</li>
              <li>Fish: 10% decay rate</li>
              <li>Herbs: 5% decay rate</li>
              <li>Grain, Hay: 1-2% decay rate</li>
              <li>Minerals and crafted goods: No decay</li>
            </ul>
          </Section>

          <Section title="Crafting System">
            <h3>Recipes</h3>
            <p>
              Agents can craft items by combining resources. Some recipes require skills.
            </p>

            <table className="docs-table">
              <thead>
                <tr>
                  <th>Recipe</th>
                  <th>Inputs</th>
                  <th>Outputs</th>
                  <th>Skill Required</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Wooden Plank</td>
                  <td>2 Wood</td>
                  <td>4 Plank</td>
                  <td>None</td>
                </tr>
                <tr>
                  <td>Bread</td>
                  <td>3 Grain, 1 Water</td>
                  <td>2 Bread (40 food value)</td>
                  <td>Cooking 1</td>
                </tr>
                <tr>
                  <td>Iron Ingot</td>
                  <td>3 Ore, 2 Wood</td>
                  <td>1 Iron Ingot</td>
                  <td>Smithing 2</td>
                </tr>
                <tr>
                  <td>Simple Tool</td>
                  <td>2 Wood, 1 Stone</td>
                  <td>1 Simple Tool</td>
                  <td>None</td>
                </tr>
                <tr>
                  <td>Rope</td>
                  <td>5 Hay</td>
                  <td>2 Rope</td>
                  <td>None</td>
                </tr>
                <tr>
                  <td>Pottery</td>
                  <td>3 Clay, 1 Water</td>
                  <td>1 Pottery</td>
                  <td>Crafting 1</td>
                </tr>
                <tr>
                  <td>Preserved Fish</td>
                  <td>2 Fish, 1 Salt</td>
                  <td>2 Preserved Fish (30 food value)</td>
                  <td>Cooking 1</td>
                </tr>
                <tr>
                  <td>Herbal Medicine</td>
                  <td>3 Herbs, 1 Water</td>
                  <td>1 Medicine</td>
                  <td>Herbalism 2</td>
                </tr>
                <tr>
                  <td>Shelter Kit</td>
                  <td>4 Plank, 2 Rope</td>
                  <td>1 Shelter Kit</td>
                  <td>Building 2, requires Simple Tool</td>
                </tr>
                <tr>
                  <td>Jewelry</td>
                  <td>1 Gem, 3 Shells</td>
                  <td>1 Jewelry</td>
                  <td>Crafting 3</td>
                </tr>
              </tbody>
            </table>

            <h3>Skill System</h3>
            <p>
              Crafting grants skill experience. Higher skills increase crafting efficiency 
              (more outputs per craft) and unlock advanced recipes.
            </p>
            <ul>
              <li><strong>Woodworking:</strong> Plank crafting efficiency</li>
              <li><strong>Cooking:</strong> Bread, Preserved Fish efficiency</li>
              <li><strong>Smithing:</strong> Iron Ingot efficiency</li>
              <li><strong>Crafting:</strong> General crafting, Pottery, Jewelry</li>
              <li><strong>Herbalism:</strong> Medicine crafting</li>
              <li><strong>Building:</strong> Shelter construction</li>
            </ul>
          </Section>

          <Section title="Agent Needs">
            <h3>Need System</h3>
            <p>
              Each agent has needs that decay over time. If needs reach 0, the agent 
              suffers penalties (reduced efficiency, inability to act).
            </p>

            <table className="docs-table">
              <thead>
                <tr>
                  <th>Need</th>
                  <th>Starting Value</th>
                  <th>Decay Rate</th>
                  <th>How to Satisfy</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Food</td>
                  <td>100</td>
                  <td>1.0/tick</td>
                  <td>Consume food items (fish, berries, bread, etc.)</td>
                </tr>
                <tr>
                  <td>Shelter</td>
                  <td>100</td>
                  <td>0.5/tick</td>
                  <td>Location shelter quality, Shelter Kit items</td>
                </tr>
                <tr>
                  <td>Reputation</td>
                  <td>50</td>
                  <td>Variable</td>
                  <td>Successful trades, contract fulfillment, social interactions</td>
                </tr>
              </tbody>
            </table>

            <h3>Agent Capacity</h3>
            <p>
              Each agent has an inventory capacity of 100 units. Agents must manage their 
              inventory carefully - full inventory prevents harvesting new resources.
            </p>
          </Section>

          <Section title="Agent Types">
            <h3>Behavioral Archetypes</h3>
            <p>
              Agents are assigned behavioral types that influence their decision-making 
              tendencies. These are not strict rules but predispositions.
            </p>

            <table className="docs-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Frequency</th>
                  <th>Primary Behaviors</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Farmer</td>
                  <td>Common (3x)</td>
                  <td>Harvesting, some trading</td>
                  <td>Focus on resource gathering, especially food crops. Provide raw materials to the economy.</td>
                </tr>
                <tr>
                  <td>Trader</td>
                  <td>Moderate (2x)</td>
                  <td>Trading, messaging, movement</td>
                  <td>Specialize in exchanging goods. Travel between locations to arbitrage price differences.</td>
                </tr>
                <tr>
                  <td>Crafter</td>
                  <td>Moderate (2x)</td>
                  <td>Crafting, some harvesting</td>
                  <td>Transform raw materials into valuable goods. Build up specialized skills.</td>
                </tr>
                <tr>
                  <td>Gatherer</td>
                  <td>Moderate (2x)</td>
                  <td>Harvesting, movement</td>
                  <td>Roam the world collecting diverse resources. Adapt to resource availability.</td>
                </tr>
                <tr>
                  <td>Leader</td>
                  <td>Rare (1x)</td>
                  <td>Group actions, messaging</td>
                  <td>Form and lead groups, propose governance rules, coordinate collective action.</td>
                </tr>
                <tr>
                  <td>Specialist</td>
                  <td>Rare (1x)</td>
                  <td>Crafting, trading</td>
                  <td>Deep expertise in specific crafts. Produce high-value specialized goods.</td>
                </tr>
                <tr>
                  <td>Cooperator</td>
                  <td>Moderate (2x)</td>
                  <td>Messaging, group actions, trading</td>
                  <td>Build relationships, join groups, facilitate cooperation between agents.</td>
                </tr>
                <tr>
                  <td>Opportunist</td>
                  <td>Rare (1x)</td>
                  <td>Trading, movement</td>
                  <td>Exploit market inefficiencies. Flexible strategies based on current conditions.</td>
                </tr>
              </tbody>
            </table>
          </Section>

          <Section title="Actions">
            <h3>Available Actions</h3>
            <p>
              Each tick, an agent can perform exactly one action:
            </p>

            <h4>MOVE</h4>
            <p>Travel to an adjacent location.</p>
            <ul>
              <li>Can only move to connected locations</li>
              <li>Travel cost based on distance and difficulty</li>
              <li>Required to access different resource types</li>
            </ul>

            <h4>HARVEST</h4>
            <p>Gather resources from the current location.</p>
            <ul>
              <li>Amount harvested depends on resource availability</li>
              <li>Requires inventory space</li>
              <li>Depletes location resources</li>
            </ul>

            <h4>CRAFT</h4>
            <p>Transform raw materials into processed goods.</p>
            <ul>
              <li>Requires recipe inputs in inventory</li>
              <li>Some recipes require minimum skill levels</li>
              <li>Some recipes require tools</li>
              <li>Grants skill experience</li>
            </ul>

            <h4>TRADE_PROPOSAL</h4>
            <p>Propose a trade to another agent at the same location.</p>
            <ul>
              <li>Specify items to offer and items to request</li>
              <li>Target agent must be at same location</li>
              <li>Creates a pending trade proposal</li>
            </ul>

            <h4>ACCEPT_TRADE</h4>
            <p>Accept or reject a pending trade proposal.</p>
            <ul>
              <li>Can only respond to proposals targeting you</li>
              <li>Must have requested items in inventory</li>
              <li>Successful trades affect reputation</li>
            </ul>

            <h4>MESSAGE</h4>
            <p>Send a message to another agent.</p>
            <ul>
              <li><strong>Direct:</strong> Private message to specific agent</li>
              <li><strong>Location:</strong> Broadcast to all agents at location</li>
              <li><strong>Group:</strong> Message to group members</li>
            </ul>

            <h4>GROUP_ACTION</h4>
            <p>Interact with social groups.</p>
            <ul>
              <li><strong>FORM_GROUP:</strong> Create a new group (guild, cooperative, etc.)</li>
              <li><strong>JOIN_GROUP:</strong> Request to join an existing group</li>
              <li><strong>LEAVE_GROUP:</strong> Leave a group you're a member of</li>
              <li><strong>VOTE:</strong> Vote on group proposals</li>
              <li><strong>PROPOSE_RULE:</strong> Propose new group rules</li>
            </ul>

            <h4>IDLE</h4>
            <p>Take no action this tick.</p>
            <ul>
              <li>Used when waiting or observing</li>
              <li>Needs still decay</li>
            </ul>
          </Section>

          <Section title="Trading & Economy">
            <h3>Barter System</h3>
            <p>
              There is <strong>no predefined currency</strong>. All trade is direct barter - 
              exchanging goods for goods. One key observation is whether agents naturally 
              converge on using certain items (like grain or gems) as a medium of exchange.
            </p>

            <h3>Trade Mechanics</h3>
            <ol>
              <li>Proposer creates trade proposal specifying offered and requested items</li>
              <li>Target agent receives proposal and can accept or reject</li>
              <li>On acceptance, items are exchanged if both parties have sufficient inventory</li>
              <li>Successful trades affect both parties' reputation</li>
            </ol>

            <h3>Price Discovery</h3>
            <p>
              The system tracks all trades to infer relative prices between items:
            </p>
            <ul>
              <li>Exchange rates calculated from trade history</li>
              <li>Prices are relative to a base item (grain by default)</li>
              <li>Price volatility tracked over time</li>
              <li>Emerging currency detection based on trade frequency</li>
            </ul>

            <h3>Contracts</h3>
            <p>
              Agents can form more complex agreements beyond single trades:
            </p>
            <ul>
              <li>Multi-party contracts with obligations</li>
              <li>Due dates for deliveries</li>
              <li>Breach penalties affecting reputation</li>
              <li>Contract fulfillment tracking</li>
            </ul>
          </Section>

          <Section title="Social Systems">
            <h3>Groups</h3>
            <p>
              Agents can form and join groups for collective action:
            </p>

            <table className="docs-table">
              <thead>
                <tr>
                  <th>Group Type</th>
                  <th>Purpose</th>
                  <th>Features</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Guild</td>
                  <td>Professional association</td>
                  <td>Skill sharing, coordinated pricing, reputation pooling</td>
                </tr>
                <tr>
                  <td>Firm</td>
                  <td>Business entity</td>
                  <td>Shared treasury, collective production</td>
                </tr>
                <tr>
                  <td>Council</td>
                  <td>Governance body</td>
                  <td>Rule-making, dispute resolution</td>
                </tr>
                <tr>
                  <td>Cooperative</td>
                  <td>Resource sharing</td>
                  <td>Pooled resources, democratic decision-making</td>
                </tr>
                <tr>
                  <td>Alliance</td>
                  <td>Mutual defense/trade</td>
                  <td>Preferential trading, information sharing</td>
                </tr>
              </tbody>
            </table>

            <h3>Group Roles</h3>
            <ul>
              <li><strong>Leader:</strong> Full control, can kick members, manage treasury</li>
              <li><strong>Officer:</strong> Can approve members, limited management</li>
              <li><strong>Member:</strong> Can vote, access group benefits</li>
              <li><strong>Applicant:</strong> Pending membership approval</li>
            </ul>

            <h3>Governance</h3>
            <p>
              Groups can establish governance systems:
            </p>
            <ul>
              <li><strong>Proposals:</strong> Members can propose rules and changes</li>
              <li><strong>Voting:</strong> Simple majority, super-majority, or unanimous</li>
              <li><strong>Rules:</strong> Taxes, resource limits, trade restrictions, membership criteria</li>
              <li><strong>Veto:</strong> Leaders can veto proposals</li>
            </ul>

            <h3>Reputation</h3>
            <p>
              Agents build reputation through their actions:
            </p>
            <ul>
              <li><strong>Trade Reliability:</strong> Successful vs failed trade ratio</li>
              <li><strong>Contract Adherence:</strong> Fulfilled vs breached contracts</li>
              <li><strong>Dispute Ratio:</strong> Involvement in disputes</li>
              <li><strong>Trust Score:</strong> Composite score (0-100) based on all factors</li>
            </ul>
          </Section>

          <Section title="Metrics & Analysis">
            <h3>Wealth Metrics</h3>
            <ul>
              <li><strong>Total Wealth:</strong> Sum of all agent inventory values</li>
              <li><strong>Mean/Median Wealth:</strong> Average wealth per agent</li>
              <li><strong>Gini Coefficient:</strong> Inequality measure (0 = perfect equality, 1 = maximum inequality)</li>
              <li><strong>Top 10% Share:</strong> Percentage of wealth held by top 10%</li>
              <li><strong>Bottom 50% Share:</strong> Percentage of wealth held by bottom 50%</li>
              <li><strong>Wealth Mobility:</strong> How much agent rankings change over time</li>
            </ul>

            <h3>Trade Network Metrics</h3>
            <ul>
              <li><strong>Node Count:</strong> Number of agents who have traded</li>
              <li><strong>Edge Count:</strong> Number of unique trading relationships</li>
              <li><strong>Density:</strong> How connected the trading network is</li>
              <li><strong>Clustering Coefficient:</strong> How cliquish the network is</li>
              <li><strong>Centrality:</strong> Which agents are most central to trade</li>
              <li><strong>Communities:</strong> Detected trading clusters</li>
            </ul>

            <h3>Specialization Metrics</h3>
            <ul>
              <li><strong>Profession Distribution:</strong> How many agents of each profession</li>
              <li><strong>Average Specialization:</strong> How focused agents are (0-1)</li>
              <li><strong>Profession Stability:</strong> How often agents change professions</li>
              <li><strong>Resource Focus:</strong> Which resources each agent concentrates on</li>
            </ul>

            <h3>Institution Metrics</h3>
            <ul>
              <li><strong>Group Count:</strong> Number of active groups</li>
              <li><strong>Average Group Size:</strong> Members per group</li>
              <li><strong>Proposals Passed/Failed:</strong> Governance activity</li>
              <li><strong>Active Contracts:</strong> Number of ongoing agreements</li>
              <li><strong>Institution Score:</strong> Composite measure of institutional development</li>
            </ul>
          </Section>

          <Section title="What to Observe">
            <h3>Early Phase (Ticks 0-100)</h3>
            <ul>
              <li>Do agents start specializing based on spawn location?</li>
              <li>What are the first trades? Are they needs-driven?</li>
              <li>Do agents naturally migrate to resource-rich areas?</li>
              <li>How quickly do trading relationships form?</li>
            </ul>

            <h3>Development Phase (Ticks 100-500)</h3>
            <ul>
              <li>Is a common medium of exchange emerging?</li>
              <li>Are professions stabilizing?</li>
              <li>Are groups forming? What types?</li>
              <li>How is wealth distribution evolving?</li>
              <li>Are trading hubs developing at specific locations?</li>
            </ul>

            <h3>Mature Phase (Ticks 500+)</h3>
            <ul>
              <li>Has a currency emerged? What item?</li>
              <li>What governance structures exist?</li>
              <li>Is there price stability?</li>
              <li>Are there persistent wealth inequalities?</li>
              <li>What institutional forms have survived?</li>
            </ul>

            <h3>Key Phenomena to Watch</h3>
            <ul>
              <li><strong>Currency Emergence:</strong> One item becoming accepted as medium of exchange</li>
              <li><strong>Market Making:</strong> Agents specializing in facilitating trades</li>
              <li><strong>Guild Formation:</strong> Professional associations forming</li>
              <li><strong>Trade Routes:</strong> Stable movement patterns for resource distribution</li>
              <li><strong>Social Stratification:</strong> Persistent wealth/role differences</li>
              <li><strong>Institutional Innovation:</strong> Novel governance or cooperation mechanisms</li>
            </ul>
          </Section>

          <Section title="Demo Mode">
            <p>
              Demo mode simulates 100 agents for 100 ticks using pre-programmed behavioral 
              patterns instead of LLM calls. This allows testing the visualization and 
              metrics without API costs.
            </p>
            <h3>Demo Limitations</h3>
            <ul>
              <li>No natural language reasoning or negotiation</li>
              <li>Simplified action selection based on probabilities</li>
              <li>No memory or learning between ticks</li>
              <li>No emergent strategies - only predefined behaviors</li>
            </ul>
            <p>
              Demo mode is useful for testing the UI and understanding the metrics, but 
              the true emergent behaviors only appear with LLM-powered agents.
            </p>
          </Section>

          <Section title="Technical Notes">
            <h3>Tick System</h3>
            <p>
              The simulation runs in discrete ticks. Each tick:
            </p>
            <ol>
              <li>Tick start event logged</li>
              <li>World update hooks run (resource regeneration)</li>
              <li>Each agent selects and executes one action</li>
              <li>After-tick hooks run (need decay, inventory decay)</li>
              <li>Metrics calculated and logged</li>
              <li>Tick end event logged</li>
            </ol>

            <h3>LLM Integration</h3>
            <p>
              In LLM mode, each agent decision involves:
            </p>
            <ol>
              <li>Building observation (current state, nearby agents, pending trades)</li>
              <li>Constructing prompt with persona, goals, and memory</li>
              <li>LLM inference to select action</li>
              <li>Action validation and execution</li>
              <li>Recording outcome in agent memory</li>
            </ol>

            <h3>Rate Limiting</h3>
            <p>
              To manage API costs, the system includes:
            </p>
            <ul>
              <li>Per-agent rate limiting</li>
              <li>Night mode (reduced activity during low-activity periods)</li>
              <li>Batched inference when possible</li>
              <li>Fallback to idle on rate limit hit</li>
            </ul>
          </Section>
        </div>
      </div>
    </div>
  )
}

export default DocsPage
