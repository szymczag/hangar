import * as React from "react";
import {
  DateLib,
  DayPicker,
  defaultLocale,
  useDayPicker,
  type DayPickerProps,
  type MonthCaptionProps,
  type MonthGridProps,
  type NavProps,
} from "react-day-picker";

import {
  CalendarView,
  CalendarViewGrid,
  CalendarViewHeader,
  CalendarViewHeading,
  CalendarViewNav,
  CalendarViewOption,
  CalendarViewSwitch,
  CalendarViewTitle,
  calendarClassNames,
} from "../../elements/calendar";
import { ChevronDownOutline, ChevronLeftOutline, ChevronRightOutline } from "../../icons";
import { NodeSlot } from "../../internal/node-slot";

type CalendarViewKind = "days" | "months" | "years";

// Figma's first 12-year page starts at 2020. Every page must use the same
// 12-year boundary, including when a chosen year opens the year view again.
const YEAR_PAGE_ANCHOR = 2020;

function yearPageFor(year: number) {
  return YEAR_PAGE_ANCHOR + Math.floor((year - YEAR_PAGE_ANCHOR) / 12) * 12;
}

/**
 * Props for Calendar. Forwards react-day-picker's DayPickerProps (mode, selected, onSelect,
 * disabled, month, defaultMonth, etc.). Styling props are omitted because propel owns the look.
 * Multiple months, native caption dropdowns, alternate nav layouts, and week numbers have no styled
 * layout here.
 */
// DayPickerProps is a discriminated union over mode. A plain Omit collapses it
// and de-correlates selected/onSelect, so omit distributively.
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
export type CalendarLabels = NonNullable<DayPickerProps["labels"]> & {
  /**
   * Accessible label for the arrow to the preceding year in month view.
   *
   * @default "Previous year"
   */
  labelPreviousYear?: () => string;
  /**
   * Accessible label for the arrow to the following year in month view.
   *
   * @default "Next year"
   */
  labelNextYear?: () => string;
  /**
   * Accessible label for the arrow to the preceding 12-year page.
   *
   * @default "Previous 12 years"
   */
  labelPreviousYearPage?: () => string;
  /**
   * Accessible label for the arrow to the following 12-year page.
   *
   * @default "Next 12 years"
   */
  labelNextYearPage?: () => string;
  /**
   * Accessible name of the month chooser for the formatted year.
   *
   * @default "Choose month for [year]"
   */
  labelMonthView?: (year: string) => string;
  /**
   * Accessible name of the year chooser for the formatted page bounds.
   *
   * @default "Choose year from [firstYear] to [lastYear]"
   */
  labelYearView?: (firstYear: string, lastYear: string) => string;
};

export type CalendarProps = DistributiveOmit<
  DayPickerProps,
  | "className"
  | "style"
  | "classNames"
  | "numberOfMonths"
  | "captionLayout"
  | "navLayout"
  | "labels"
  | "showWeekNumber"
> & {
  /** DayPicker labels, with optional labels for Calendar's month and year views. */
  labels?: CalendarLabels;
  /**
   * Initial calendar view.
   *
   * @default "days"
   */
  defaultView?: CalendarViewKind;
};

type CalendarViewState = {
  view: CalendarViewKind;
  setView: React.Dispatch<React.SetStateAction<CalendarViewKind>>;
  candidateYear: number;
  setCandidateYear: React.Dispatch<React.SetStateAction<number>>;
  yearPageStart: number;
  setYearPageStart: React.Dispatch<React.SetStateAction<number>>;
  calendarLabels?: CalendarLabels;
};

const CalendarViewContext = React.createContext<CalendarViewState | null>(null);

function useCalendarView() {
  const context = React.useContext(CalendarViewContext);
  if (!context) throw new Error("Calendar view must be rendered inside Calendar");
  return context;
}

function useCalendarDateLib() {
  const { dayPickerProps } = useDayPicker();
  return React.useMemo(
    () =>
      new DateLib(
        {
          locale: { ...defaultLocale, ...dayPickerProps.locale },
          timeZone: dayPickerProps.timeZone,
          numerals: dayPickerProps.numerals,
        },
        dayPickerProps.dateLib,
      ),
    [
      dayPickerProps.locale,
      dayPickerProps.timeZone,
      dayPickerProps.numerals,
      dayPickerProps.dateLib,
    ],
  );
}

function monthKey(year: number, monthIndex: number) {
  return year * 12 + monthIndex;
}

function isMonthInRange(year: number, monthIndex: number, props: DayPickerProps) {
  const key = monthKey(year, monthIndex);
  return (
    !props.disableNavigation &&
    (!props.startMonth ||
      key >= monthKey(props.startMonth.getFullYear(), props.startMonth.getMonth())) &&
    (!props.endMonth || key <= monthKey(props.endMonth.getFullYear(), props.endMonth.getMonth()))
  );
}

function isYearInRange(year: number, props: DayPickerProps) {
  return (
    !props.disableNavigation &&
    (!props.startMonth || year >= props.startMonth.getFullYear()) &&
    (!props.endMonth || year <= props.endMonth.getFullYear())
  );
}

// Hoisted so react-day-picker does not remount the chevrons on each render.
const renderChevron: NonNullable<DayPickerProps["components"]>["Chevron"] = ({
  orientation,
  className,
}) =>
  orientation === "left" ? (
    <ChevronLeftOutline aria-hidden className={className} />
  ) : (
    <ChevronRightOutline aria-hidden className={className} />
  );

function CalendarMonthCaption({ calendarMonth }: MonthCaptionProps) {
  const { view, setView, candidateYear, setCandidateYear, yearPageStart, setYearPageStart } =
    useCalendarView();
  const { dayPickerProps, formatters, labels } = useDayPicker();
  const dateLib = useCalendarDateLib();
  const displayedMonth = calendarMonth.date;
  const displayedYear = displayedMonth.getFullYear();
  const monthSwitchRef = React.useRef<HTMLButtonElement>(null);
  const previousViewRef = React.useRef(view);

  React.useEffect(() => {
    setCandidateYear(displayedYear);
    setYearPageStart(yearPageFor(displayedYear));
  }, [displayedYear, setCandidateYear, setYearPageStart]);

  React.useEffect(() => {
    if (view === "days" && previousViewRef.current !== "days") monthSwitchRef.current?.focus();
    previousViewRef.current = view;
  }, [view]);

  const showMonths = () => {
    setCandidateYear(displayedYear);
    setView("months");
  };
  const showYears = (year: number) => {
    setCandidateYear(year);
    setYearPageStart(yearPageFor(year));
    setView("years");
  };
  const monthLabel = dayPickerProps.formatters?.formatMonthDropdown
    ? formatters.formatMonthDropdown(displayedMonth, dateLib)
    : dateLib.format(displayedMonth, "MMM");
  const yearLabel = (year: number) =>
    formatters.formatYearDropdown(dateLib.newDate(year, 0, 1), dateLib);
  const monthSwitchLabel = `${labels.labelMonthDropdown(dateLib.options)}, ${dateLib.format(displayedMonth, "MMMM")}`;
  const yearSwitchLabel = (year: number) =>
    `${labels.labelYearDropdown(dateLib.options)}, ${yearLabel(year)}`;

  const monthSwitch = (
    <CalendarViewSwitch
      ref={monthSwitchRef}
      type="button"
      aria-label={monthSwitchLabel}
      disabled={dayPickerProps.disableNavigation}
      onClick={showMonths}
    >
      {monthLabel}
      <NodeSlot>
        <ChevronDownOutline aria-hidden />
      </NodeSlot>
    </CalendarViewSwitch>
  );
  const yearSwitch = (
    <CalendarViewSwitch
      type="button"
      aria-label={yearSwitchLabel(displayedYear)}
      disabled={dayPickerProps.disableNavigation}
      onClick={() => showYears(displayedYear)}
    >
      {yearLabel(displayedYear)}
      <NodeSlot>
        <ChevronDownOutline aria-hidden />
      </NodeSlot>
    </CalendarViewSwitch>
  );

  return (
    <CalendarViewHeader>
      <CalendarViewHeading aria-live="polite" aria-atomic="true">
        {view === "days" ? (
          <>
            {dateLib.getMonthYearOrder() === "year-first" ? (
              <>
                {yearSwitch}
                {monthSwitch}
              </>
            ) : (
              <>
                {monthSwitch}
                {yearSwitch}
              </>
            )}
          </>
        ) : view === "months" ? (
          <CalendarViewSwitch
            type="button"
            aria-label={yearSwitchLabel(candidateYear)}
            disabled={dayPickerProps.disableNavigation}
            onClick={() => showYears(candidateYear)}
          >
            {yearLabel(candidateYear)}
            <NodeSlot>
              <ChevronDownOutline aria-hidden />
            </NodeSlot>
          </CalendarViewSwitch>
        ) : (
          <CalendarViewTitle>
            {dateLib.formatNumber(yearPageStart)}–{dateLib.formatNumber(yearPageStart + 11)}
          </CalendarViewTitle>
        )}
      </CalendarViewHeading>
    </CalendarViewHeader>
  );
}

function CalendarNav({ onPreviousClick, onNextClick, previousMonth, nextMonth }: NavProps) {
  const { view, candidateYear, setCandidateYear, yearPageStart, setYearPageStart, calendarLabels } =
    useCalendarView();
  const { components, classNames, labels, dayPickerProps } = useDayPicker();

  const previousEnabled =
    view === "days"
      ? Boolean(previousMonth)
      : view === "months"
        ? isYearInRange(candidateYear - 1, dayPickerProps)
        : Array.from({ length: 12 }, (_, index) => yearPageStart - 12 + index).some((year) =>
            isYearInRange(year, dayPickerProps),
          );
  const nextEnabled =
    view === "days"
      ? Boolean(nextMonth)
      : view === "months"
        ? isYearInRange(candidateYear + 1, dayPickerProps)
        : Array.from({ length: 12 }, (_, index) => yearPageStart + 12 + index).some((year) =>
            isYearInRange(year, dayPickerProps),
          );
  const previousLabel =
    view === "days"
      ? labels.labelPrevious(previousMonth)
      : view === "months"
        ? (calendarLabels?.labelPreviousYear?.() ?? "Previous year")
        : (calendarLabels?.labelPreviousYearPage?.() ?? "Previous 12 years");
  const nextLabel =
    view === "days"
      ? labels.labelNext(nextMonth)
      : view === "months"
        ? (calendarLabels?.labelNextYear?.() ?? "Next year")
        : (calendarLabels?.labelNextYearPage?.() ?? "Next 12 years");

  return (
    <CalendarViewNav>
      <components.PreviousMonthButton
        type="button"
        className={classNames.button_previous}
        aria-label={previousLabel}
        disabled={!previousEnabled}
        onClick={(event) => {
          if (view === "days") onPreviousClick?.(event);
          else if (view === "months") setCandidateYear((year) => year - 1);
          else setYearPageStart((year) => year - 12);
        }}
      >
        <components.Chevron
          orientation="left"
          className={classNames.chevron}
          disabled={!previousEnabled}
        />
      </components.PreviousMonthButton>
      <components.NextMonthButton
        type="button"
        className={classNames.button_next}
        aria-label={nextLabel}
        disabled={!nextEnabled}
        onClick={(event) => {
          if (view === "days") onNextClick?.(event);
          else if (view === "months") setCandidateYear((year) => year + 1);
          else setYearPageStart((year) => year + 12);
        }}
      >
        <components.Chevron
          orientation="right"
          className={classNames.chevron}
          disabled={!nextEnabled}
        />
      </components.NextMonthButton>
    </CalendarViewNav>
  );
}

function CalendarMonthGrid(props: MonthGridProps) {
  const { view, setView, candidateYear, setCandidateYear, yearPageStart, calendarLabels } =
    useCalendarView();
  const { months, goToMonth, dayPickerProps, formatters } = useDayPicker();
  const dateLib = useCalendarDateLib();
  const displayedMonth = months[0]?.date;
  const [focusedIndex, setFocusedIndex] = React.useState<number | null>(null);
  const optionRefs = React.useRef<Array<HTMLButtonElement | null>>([]);
  const previousViewRef = React.useRef<CalendarViewKind>(view);

  const options = React.useMemo(() => Array.from({ length: 12 }, (_, index) => index), []);
  const isEnabled = (index: number) =>
    view === "months"
      ? isMonthInRange(candidateYear, index, dayPickerProps)
      : isYearInRange(yearPageStart + index, dayPickerProps);
  const currentIndex =
    view === "months"
      ? displayedMonth?.getFullYear() === candidateYear
        ? displayedMonth.getMonth()
        : 0
      : candidateYear >= yearPageStart && candidateYear < yearPageStart + 12
        ? candidateYear - yearPageStart
        : 0;
  const firstEnabled = options.find(isEnabled) ?? 0;
  const initialIndex = isEnabled(currentIndex) ? currentIndex : firstEnabled;
  const tabStopIndex =
    focusedIndex !== null && isEnabled(focusedIndex) ? focusedIndex : initialIndex;

  React.useEffect(() => {
    if (view !== "days" && previousViewRef.current !== view) {
      setFocusedIndex(initialIndex);
      optionRefs.current[initialIndex]?.focus();
    }
    previousViewRef.current = view;
  }, [view, initialIndex]);

  if (view === "days") return <table {...props} />;

  const moveFocus = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const horizontalDirection = dayPickerProps.dir === "rtl" ? -1 : 1;
    const step =
      event.key === "ArrowRight"
        ? horizontalDirection
        : event.key === "ArrowLeft"
          ? -horizontalDirection
          : event.key === "ArrowDown"
            ? 3
            : event.key === "ArrowUp"
              ? -3
              : 0;
    let target = index;
    if (event.key === "Home") target = firstEnabled;
    else if (event.key === "End")
      target = options.slice().reverse().find(isEnabled) ?? firstEnabled;
    else if (step !== 0) {
      target += step;
      while (target >= 0 && target < 12 && !isEnabled(target)) target += step;
      if (target < 0 || target >= 12) return;
    } else return;
    event.preventDefault();
    setFocusedIndex(target);
    optionRefs.current[target]?.focus();
  };

  return (
    <CalendarView
      role="group"
      aria-label={
        view === "months"
          ? (calendarLabels?.labelMonthView?.(dateLib.formatNumber(candidateYear)) ??
            "Choose month for " + dateLib.formatNumber(candidateYear))
          : (calendarLabels?.labelYearView?.(
              dateLib.formatNumber(yearPageStart),
              dateLib.formatNumber(yearPageStart + 11),
            ) ??
            "Choose year from " +
              dateLib.formatNumber(yearPageStart) +
              " to " +
              dateLib.formatNumber(yearPageStart + 11))
      }
    >
      <CalendarViewGrid>
        {options.map((index) => {
          const year = view === "months" ? candidateYear : yearPageStart + index;
          const monthDate = dateLib.newDate(year, index, 1);
          const yearDate = dateLib.newDate(year, 0, 1);
          const optionText =
            view === "months"
              ? dayPickerProps.formatters?.formatMonthDropdown
                ? formatters.formatMonthDropdown(monthDate, dateLib)
                : dateLib.format(monthDate, "MMM")
              : formatters.formatYearDropdown(yearDate, dateLib);
          const active =
            view === "months"
              ? displayedMonth?.getFullYear() === candidateYear &&
                displayedMonth.getMonth() === index
              : candidateYear === year;
          const label = view === "months" ? dateLib.formatMonthYear(monthDate) : optionText;
          return (
            <CalendarViewOption
              key={index}
              ref={(node) => {
                optionRefs.current[index] = node;
              }}
              type="button"
              data-active={active ? "" : undefined}
              aria-label={label}
              aria-current={active ? "true" : undefined}
              disabled={!isEnabled(index)}
              tabIndex={index === tabStopIndex ? 0 : -1}
              onFocus={() => setFocusedIndex(index)}
              onKeyDown={(event) => moveFocus(event, index)}
              onClick={() => {
                if (view === "months") {
                  goToMonth(monthDate);
                  setView("days");
                } else {
                  setCandidateYear(year);
                  setView("months");
                }
              }}
            >
              {optionText}
            </CalendarViewOption>
          );
        })}
      </CalendarViewGrid>
    </CalendarView>
  );
}

/**
 * A bare calendar with day, month, and year navigation. Day selection, disabled dates, keyboard
 * movement within the day grid, and controlled month/onMonthChange are handled by react-day-picker.
 * Month and year browsing changes the displayed month only after a month is chosen. A popover,
 * dialog, or card supplies the surrounding surface and gutters. Weeks start on Monday by default;
 * pass `weekStartsOn` to override this.
 */
export function Calendar({ defaultView = "days", labels, ...props }: CalendarProps) {
  const initialDate = props.month ?? props.defaultMonth ?? props.today ?? new Date();
  const [view, setView] = React.useState<CalendarViewKind>(
    props.disableNavigation ? "days" : defaultView,
  );
  const [candidateYear, setCandidateYear] = React.useState(initialDate.getFullYear());
  const [yearPageStart, setYearPageStart] = React.useState(yearPageFor(initialDate.getFullYear()));

  React.useEffect(() => {
    if (props.disableNavigation) setView("days");
  }, [props.disableNavigation]);

  return (
    <CalendarViewContext.Provider
      value={{
        view,
        setView,
        candidateYear,
        setCandidateYear,
        yearPageStart,
        setYearPageStart,
        calendarLabels: labels,
      }}
    >
      <DayPicker
        weekStartsOn={1}
        classNames={calendarClassNames}
        {...props}
        navLayout="after"
        labels={labels}
        components={{
          Chevron: renderChevron,
          MonthCaption: CalendarMonthCaption,
          MonthGrid: CalendarMonthGrid,
          Nav: CalendarNav,
          ...props.components,
        }}
      />
    </CalendarViewContext.Provider>
  );
}
