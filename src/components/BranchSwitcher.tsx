/**
 * BranchSwitcher - Professional branch/company switcher component
 * With search, recent selections, and keyboard navigation.
 */
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  Building2,
  Check,
  ChevronDown,
  Search,
  PlusCircle,
  MapPin,
  Star,
  Clock,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

export interface Branch {
  id: string;
  name: string;
  company?: string;
  city?: string;
  address?: string;
  icon?: LucideIcon;
  isFavorite?: boolean;
  isRecent?: boolean;
}

export interface BranchSwitcherProps {
  branches: Branch[];
  selectedBranchId: string;
  onBranchChange: (branchId: string) => void;
  onAddBranch?: () => void;
  onManageBranches?: () => void;
  disabled?: boolean;
  className?: string;
  label?: string;
}

// ─── Default branch data ─────────────────────────────────

export const defaultBranches: Branch[] = [
  {
    id: "all",
    name: "Tüm Şubeler",
    company: "FoodFlow Azerbaijan",
    city: "Tüm Şehirler",
    icon: Building2,
    isFavorite: true,
  },
  {
    id: "nizami",
    name: "Nizami Şubesi",
    company: "FoodFlow Azerbaijan",
    city: "Bakü",
    address: "Nizami Caddesi 45",
    icon: Building2,
    isFavorite: true,
  },
  {
    id: "gencik",
    name: "Gənclik Şubesi",
    company: "FoodFlow Azerbaijan",
    city: "Bakü",
    address: "Gənclik Bulvarı 12",
    icon: Building2,
  },
  {
    id: "28may",
    name: "28 May Şubesi",
    company: "FoodFlow Azerbaijan",
    city: "Bakü",
    address: "28 May Caddesi 78",
    icon: Building2,
    isRecent: true,
  },
];

// ─── Component ───────────────────────────────────────────

export default function BranchSwitcher({
  branches,
  selectedBranchId,
  onBranchChange,
  onAddBranch,
  onManageBranches,
  disabled = false,
  className,
  label,
}: BranchSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const selectedBranch = useMemo(
    () => branches.find((b) => b.id === selectedBranchId) || branches[0],
    [branches, selectedBranchId]
  );

  // Filter branches by search query
  const filteredBranches = useMemo(() => {
    if (!searchQuery.trim()) return branches;
    const q = searchQuery.toLowerCase();
    return branches.filter(
      (b) =>
        b.name.toLowerCase().includes(q) ||
        b.city?.toLowerCase().includes(q) ||
        b.company?.toLowerCase().includes(q)
    );
  }, [branches, searchQuery]);

  // Group: Favorites, Recent, Others
  const grouped = useMemo(() => {
    const favorites = filteredBranches.filter((b) => b.isFavorite);
    const recent = filteredBranches.filter(
      (b) => b.isRecent && !b.isFavorite
    );
    const others = filteredBranches.filter(
      (b) => !b.isFavorite && !b.isRecent
    );
    return { favorites, recent, others };
  }, [filteredBranches]);

  const flatList = useMemo(
    () => [...grouped.favorites, ...grouped.recent, ...grouped.others],
    [grouped]
  );

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setSearchQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Focus search on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
      setHighlightedIndex(0);
    }
  }, [isOpen]);

  // Scroll highlighted into view
  useEffect(() => {
    if (listRef.current && isOpen) {
      const el = listRef.current.children[highlightedIndex] as HTMLElement;
      if (el) {
        el.scrollIntoView({ block: "nearest" });
      }
    }
  }, [highlightedIndex, isOpen]);

  const handleSelect = useCallback(
    (branchId: string) => {
      onBranchChange(branchId);
      setIsOpen(false);
      setSearchQuery("");
    },
    [onBranchChange]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) return;
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setHighlightedIndex((prev) =>
            Math.min(prev + 1, flatList.length - 1)
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setHighlightedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (flatList[highlightedIndex]) {
            handleSelect(flatList[highlightedIndex].id);
          }
          break;
        case "Escape":
          e.preventDefault();
          setIsOpen(false);
          setSearchQuery("");
          break;
      }
    },
    [isOpen, flatList, highlightedIndex, handleSelect]
  );

  return (
    <div
      ref={containerRef}
      className={cn("relative", className)}
      onKeyDown={handleKeyDown}
    >
      {label && (
        <label className="block text-xs font-medium text-[#94A3B8] mb-1.5 uppercase tracking-wide">
          {label}
        </label>
      )}

      {/* Trigger button */}
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex items-center gap-2 w-full h-10 px-3 rounded-lg border transition-all duration-200",
          "text-sm text-[#0F172A] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED] focus-visible:ring-offset-1",
          isOpen
            ? "border-[#7C3AED] bg-[#F5F3FF] shadow-sm"
            : "border-[#E2E8F0] bg-white hover:border-[#CBD5E1] hover:bg-[#F8FAFC]",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <Building2 className="w-4 h-4 text-[#475569] shrink-0" />
        <span className="flex-1 text-left truncate">
          {selectedBranch?.name || "Şube Seçin"}
        </span>
        <ChevronDown
          className={cn(
            "w-4 h-4 text-[#94A3B8] transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute z-50 w-full mt-1.5 bg-white rounded-xl border border-[#E2E8F0] shadow-lg overflow-hidden"
          role="listbox"
        >
          {/* Search */}
          <div className="px-3 pt-3 pb-2">
            <div className="flex items-center gap-2 bg-[#F1F5F9] rounded-lg px-3 h-9">
              <Search className="w-3.5 h-3.5 text-[#94A3B8] shrink-0" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setHighlightedIndex(0);
                }}
                placeholder="Şube ara..."
                className="bg-transparent border-none outline-none text-sm text-[#0F172A] placeholder-[#94A3B8] flex-1"
              />
            </div>
          </div>

          {/* Branch list */}
          <div
            ref={listRef}
            className="max-h-[280px] overflow-y-auto py-1"
          >
            {flatList.length === 0 && (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-[#94A3B8]">Sonuç bulunamadı</p>
              </div>
            )}

            {/* Favorites */}
            {grouped.favorites.length > 0 && (
              <>
                <div className="px-3 py-1.5">
                  <span className="text-[10px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                    <Star className="w-3 h-3 inline -mt-px mr-1" />
                    Favoriler
                  </span>
                </div>
                {grouped.favorites.map((branch, idx) => (
                  <BranchItem
                    key={branch.id}
                    branch={branch}
                    isSelected={branch.id === selectedBranchId}
                    isHighlighted={idx === highlightedIndex}
                    onSelect={() => handleSelect(branch.id)}
                  />
                ))}
              </>
            )}

            {/* Recent */}
            {grouped.recent.length > 0 && (
              <>
                <div className="px-3 py-1.5 border-t border-[#F1F5F9]">
                  <span className="text-[10px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                    <Clock className="w-3 h-3 inline -mt-px mr-1" />
                    Son Kullanılan
                  </span>
                </div>
                {grouped.recent.map((branch, idx) => {
                  const actualIdx = grouped.favorites.length + idx;
                  return (
                    <BranchItem
                      key={branch.id}
                      branch={branch}
                      isSelected={branch.id === selectedBranchId}
                      isHighlighted={actualIdx === highlightedIndex}
                      onSelect={() => handleSelect(branch.id)}
                    />
                  );
                })}
              </>
            )}

            {/* Others */}
            {grouped.others.length > 0 && (
              <>
                {(grouped.favorites.length > 0 || grouped.recent.length > 0) && (
                  <div className="px-3 py-1.5 border-t border-[#F1F5F9]">
                    <span className="text-[10px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                      <Building2 className="w-3 h-3 inline -mt-px mr-1" />
                      Tüm Şubeler
                    </span>
                  </div>
                )}
                {grouped.others.map((branch, idx) => {
                  const actualIdx =
                    grouped.favorites.length + grouped.recent.length + idx;
                  return (
                    <BranchItem
                      key={branch.id}
                      branch={branch}
                      isSelected={branch.id === selectedBranchId}
                      isHighlighted={actualIdx === highlightedIndex}
                      onSelect={() => handleSelect(branch.id)}
                    />
                  );
                })}
              </>
            )}
          </div>

          {/* Footer actions */}
          <div className="border-t border-[#F1F5F9] px-2 py-1.5">
            {onAddBranch && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  onAddBranch();
                }}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#475569] hover:bg-[#F8FAFC] hover:text-[#2563EB] rounded-lg transition-colors"
              >
                <PlusCircle className="w-4 h-4" />
                Yeni Şube Ekle
              </button>
            )}
            {onManageBranches && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  onManageBranches();
                }}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#475569] hover:bg-[#F8FAFC] hover:text-[#2563EB] rounded-lg transition-colors"
              >
                <Building2 className="w-4 h-4" />
                Şubeleri Yönet
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Branch Item ─────────────────────────────────────────

function BranchItem({
  branch,
  isSelected,
  isHighlighted,
  onSelect,
}: {
  branch: Branch;
  isSelected: boolean;
  isHighlighted: boolean;
  onSelect: () => void;
}) {
  const Icon = branch.icon || Building2;

  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex items-center gap-3 w-full px-3 py-2.5 text-sm transition-colors text-left",
        isSelected
          ? "bg-[#F1F5F9] text-[#2563EB] font-medium"
          : "text-[#0F172A] hover:bg-[#F8FAFC]",
        isHighlighted && !isSelected && "bg-[#F8FAFC]"
      )}
      role="option"
      aria-selected={isSelected}
    >
      <Icon
        className={cn(
          "w-4 h-4 shrink-0",
          isSelected ? "text-[#2563EB]" : "text-[#94A3B8]"
        )}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="truncate">{branch.name}</span>
          {branch.isFavorite && (
            <Star className="w-3 h-3 text-[#D97706] shrink-0" />
          )}
        </div>
        {branch.city && (
          <span className="text-[11px] text-[#94A3B8] flex items-center gap-1">
            <MapPin className="w-2.5 h-2.5" />
            {branch.city}
          </span>
        )}
      </div>
      {isSelected && <Check className="w-4 h-4 text-[#2563EB] shrink-0" />}
    </button>
  );
}
