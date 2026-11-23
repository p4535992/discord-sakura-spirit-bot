# Sakura Spirit Bot - System Architecture

## Technology Stack

### Core Framework
- **Discord.py** (v2.3+): Primary Discord API wrapper
- **Python 3.11+**: Runtime environment
- **PostgreSQL**: Primary persistent storage
- **Redis**: Caching and real-time state management

### AI & Intelligence
- **OpenAI API**: Spirit personality generation, dream content, lore generation
- **Custom AI Engine**: Emotional state tracking, relationship modeling

### Additional Libraries
- **asyncio**: Asynchronous task management
- **APScheduler**: Scheduled events (weather changes, spirit roaming)
- **SQLAlchemy**: ORM for database operations
- **Pydantic**: Data validation and settings management
- **aiohttp**: External API calls (game stats)

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Discord Gateway                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Bot Core (discord.py)                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Command Handler & Event Router             │    │
│  └────────────────────────────────────────────────────┘    │
└───────┬──────────┬──────────┬──────────┬──────────┬─────────┘
        │          │          │          │          │
┌───────▼────┐ ┌──▼──────┐ ┌─▼─────┐ ┌─▼──────┐ ┌─▼────────┐
│  Spirit    │ │ Weather │ │Social │ │Gaming  │ │ World    │
│  System    │ │ System  │ │Engine │ │Utils   │ │ System   │
└───────┬────┘ └──┬──────┘ └─┬─────┘ └─┬──────┘ └─┬────────┘
        │         │           │         │          │
        └─────────┴───────────┴─────────┴──────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
┌───────▼────────┐                      ┌──────────▼─────────┐
│   PostgreSQL   │                      │      Redis         │
│  (Persistence) │                      │   (Real-time)      │
└────────────────┘                      └────────────────────┘
```

## Module Breakdown

All module paths are relative to `sakura-bot/`, the application root and the
image build context.

### 1. Core Modules

#### Bot Core (`core/`)
- `bot.py`: Main bot instance and initialization
- `config.py`: Configuration management
- `database.py`: Database connection and session management
- `cache.py`: Redis connection and caching utilities
- `events.py`: Global event listeners

#### Command System (`commands/`)
- `spirit_commands.py`: Spirit interaction commands
- `weather_commands.py`: Weather system commands
- `social_commands.py`: Social features
- `gaming_commands.py`: LFG and gaming utilities
- `world_commands.py`: Sakura Park exploration
- `admin_commands.py`: Administrative controls

### 2. Feature Modules

#### Spirit System (`systems/spirits/`)
- `spirit_ai.py`: AI-driven spirit behavior engine
- `spirit_manager.py`: Spirit lifecycle management
- `spirit_roaming.py`: Autonomous roaming logic
- `spirit_companions.py`: User companion system
- `spirit_factions.py`: Faction dynamics

#### Weather System (`systems/weather/`)
- `weather_engine.py`: Weather rotation and effects
- `weather_types.py`: Weather type definitions
- `weather_effects.py`: Impact on other systems

#### Social Engine (`systems/social/`)
- `emotional_engine.py`: User emotional state tracking
- `relationship_tracker.py`: User-to-user relationships
- `dream_system.py`: Daily dream generation
- `post_office.py`: Letter and gift system

#### Gaming Utilities (`systems/gaming/`)
- `lfg_manager.py`: LFG queue and team formation
- `voice_monitor.py`: Voice channel activity tracking
- `game_api.py`: External game API integrations
- `ritual_buffs.py`: Pre-game ritual system

#### World System (`systems/world/`)
- `park_manager.py`: Sakura Park zone management
- `npc_system.py`: NPC behavior and schedules
- `shop_system.py`: Shop inventory and transactions
- `exploration.py`: Zone exploration mechanics
- `mini_games.py`: Park mini-games

#### Gacha & Cosmetics (`systems/gacha/`)
- `gacha_engine.py`: Pull mechanics and rarity calculation
- `cosmetics_manager.py`: Cosmetic item management
- `inventory_system.py`: User inventory

#### Lore System (`systems/lore/`)
- `codex_manager.py`: Lore generation and storage
- `timeline_tracker.py`: Server timeline management
- `legend_generator.py`: User legend creation

#### Events System (`systems/events/`)
- `ritual_circles.py`: Cooperative ritual mechanics
- `world_boss.py`: Boss encounter system
- `event_spawner.py`: Dynamic event generation

### 3. Data Models (`models/`)

#### User Models
```python
- User: Core user profile
- UserSpirit: Companion spirit data
- UserInventory: Item ownership
- UserStats: XP, level, achievements
- UserEmotionalState: Emotional tracking
```

#### Server Models
```python
- Server: Server configuration
- ServerWeather: Current weather state
- ServerHarmony: Harmony score tracking
- ServerFaction: Faction dominance
```

#### Spirit Models
```python
- Spirit: Spirit entity definition
- SpiritAttribute: Spirit stats and traits
- SpiritInteraction: Interaction history
```

#### World Models
```python
- ParkZone: Zone definitions
- NPC: NPC data
- Shop: Shop inventory
- WorldEvent: Event records
```

#### Lore Models
```python
- CodexEntry: Lore pages
- Timeline: Server timeline
- Legend: User legends
```

### 4. Utilities (`utils/`)
- `embed_builder.py`: Aesthetic embed templates
- `rate_limiter.py`: Discord rate limit handling
- `scheduler.py`: Task scheduling utilities
- `validators.py`: Input validation
- `formatters.py`: Text and data formatting
- `ai_helpers.py`: AI prompt templates and helpers

## Database Schema Design

### Core Tables

**users**
- id (PK)
- discord_id (unique)
- username
- xp
- level
- emotional_state
- aura_type
- created_at
- last_active

**user_spirits**
- id (PK)
- user_id (FK)
- spirit_id (FK)
- name
- mood
- power_level
- evolution_stage
- acquired_at

**user_inventory**
- id (PK)
- user_id (FK)
- item_type
- item_id
- quantity
- acquired_at

**servers**
- id (PK)
- discord_id (unique)
- harmony_score
- current_weather
- weather_changed_at
- faction_dominance
- config_json

**spirits**
- id (PK)
- name
- rarity
- faction
- attributes_json
- behavior_profile

**weather_history**
- id (PK)
- server_id (FK)
- weather_type
- started_at
- ended_at
- triggered_by

**relationships**
- id (PK)
- user_id_1 (FK)
- user_id_2 (FK)
- warmth_score
- rivalry_score
- synergy_score
- chaos_score

**codex_entries**
- id (PK)
- server_id (FK)
- title
- content
- category
- unlocked_by
- created_at

**world_events**
- id (PK)
- server_id (FK)
- event_type
- participants_json
- outcome_json
- timestamp

## Real-Time Systems (Redis)

### Cache Keys Structure
```
server:{server_id}:weather:current
server:{server_id}:harmony:score
server:{server_id}:active_users
user:{user_id}:emotional_state
user:{user_id}:daily_dream
spirit:roaming:schedule
event:active:{event_id}
lfg:queue:{game_type}
ritual:active:{ritual_id}
```

## Event-Driven Architecture

### Event Flow
1. **User Action** → Discord Event
2. **Event Router** → Appropriate Handler
3. **Handler** → Update State (DB + Cache)
4. **State Change** → Trigger Side Effects
5. **Side Effects** → Update Related Systems
6. **Response** → Send to Discord

### Key Events
- `on_message`: XP gain, emotional tracking, spirit reactions
- `on_voice_state_update`: LFG detection, voice monitoring
- `on_member_join`: Welcome ritual, initial setup
- `on_reaction_add`: Ritual participation, voting
- Scheduled: Weather changes, spirit roaming, dream generation

## Scalability Considerations

### Performance Optimizations
1. **Caching Strategy**: Frequently accessed data in Redis
2. **Database Indexing**: Optimize queries on user_id, server_id
3. **Async Operations**: All I/O operations asynchronous
4. **Rate Limiting**: Respect Discord API limits
5. **Connection Pooling**: Reuse database connections

### Modular Design
- Each system can be enabled/disabled per server
- Feature flags in server configuration
- Graceful degradation if external services fail

## Security & Privacy

### Data Protection
- No DM logging or storage
- GDPR-compliant data deletion command
- Encrypted sensitive data (API keys)
- Rate limiting to prevent abuse

### Permission Management
- Role-based access control
- Admin-only configuration commands
- User consent for data collection

## Deployment Architecture

```
┌─────────────────────────────────────────────────┐
│              Docker Container                    │
│  ┌───────────────────────────────────────┐     │
│  │      Sakura Spirit Bot Process        │     │
│  └───────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
┌───────▼────┐ ┌───▼─────┐ ┌──▼──────┐
│ PostgreSQL │ │  Redis  │ │ OpenAI  │
│  Database  │ │  Cache  │ │   API   │
└────────────┘ └─────────┘ └─────────┘
```

### Environment Variables
```
SAKURA_BOT_DISCORD_TOKEN
SAKURA_BOT_OPENAI_API_KEY
SAKURA_BOT_DATABASE_URL
SAKURA_BOT_REDIS_URL
SAKURA_BOT_ENVIRONMENT (development/production)
```

Variables are prefixed with the container that reads them (`SAKURA_BOT_*`,
`SAKURA_POSTGRES_*`, `SAKURA_REDIS_*`, `SAKURA_PROXY_*`,
`SAKURA_PROXY_LOGROTATE_*`); Compose maps the PostgreSQL keys to the
`POSTGRES_*` names the official image requires.

## Development Phases

1. **Phase 1**: Core bot + database setup
2. **Phase 2**: Spirit system + weather system
3. **Phase 3**: Social features + emotional engine
4. **Phase 4**: Gaming utilities + LFG
5. **Phase 5**: Sakura Park + world system
6. **Phase 6**: Gacha + cosmetics
7. **Phase 7**: Events + rituals + boss fights
8. **Phase 8**: Testing + optimization
9. **Phase 9**: Documentation + deployment

## API Integration Points

### External APIs
- **Discord API**: Primary interface
- **OpenAI API**: AI-generated content
- **Valorant API**: Game stats (if available)
- **Riot Games API**: League stats
- **Steam API**: General game data

### Internal APIs
- REST endpoints for web dashboard (future)
- WebSocket for real-time updates (future)
