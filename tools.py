import numpy as np
import re
import pandas as pd




def get_interval_boundaries(expression):
    def parse_range_inequality(expression):
        pattern = r'^\s*([-+]?\d+(\.\d+)?)?\s*([<>=]=?)\s*(\w+)\s*(?:(?:(<=)|(<))\s*([-+]?\d+(\.\d+)?))?\s*(?:(?:(>=)|(>))\s*([-+]?\d+(\.\d+)?))?$'
        match = re.match(pattern, expression)

        if match:
            lower_bound = match.group(1)
            lower_operator = match.group(3)
            variable = match.group(4)
            upper_operator = match.group(6) or match.group(8)
            upper_bound = match.group(7) or match.group(10)

            if lower_bound is None or upper_bound is None:
                return None, None

            try:
                lower_bound = float(lower_bound)
                if (lower_bound).is_integer():
                    lower_bound = int(lower_bound)
            except (ValueError, TypeError):
                lower_bound = None

            try:
                upper_bound = float(upper_bound)
                if (upper_bound).is_integer():
                    upper_bound = int(upper_bound)
            except (ValueError, TypeError):
                upper_bound = None

            if lower_bound is not None and upper_bound is not None and lower_bound < upper_bound \
                    and (lower_operator in ['<=', '<', None] and upper_operator in ['<=', '<', None]):
                return lower_bound, upper_bound

        return None, None

    def parse_range_closed(expression):
        pattern = r'^([-+]?\d+(\.\d+)?)?([<>=]=?)?x?([-+]?\d+(\.\d+)?)?\s*-\s*([-+]?\d+(\.\d+)?)?([<>=]=?)?x?([-+]?\d+(\.\d+)?)?$'
        match = re.match(pattern, expression)

        if match:
            lower_bound = match.group(1) or match.group(4)
            upper_bound = match.group(6) or match.group(9)

            if lower_bound is None or upper_bound is None:
                return None, None

            lower_bound = float(lower_bound)
            upper_bound = float(upper_bound)

            if (lower_bound).is_integer():
                lower_bound = int(lower_bound)
            if (upper_bound).is_integer():
                upper_bound = int(upper_bound)

            if lower_bound < upper_bound:
                return lower_bound, upper_bound

        return None, None

    def parse_range(expression):
        if isinstance(expression, (float, int)):
            expression = str(expression)

        if re.search(r'[<>=]', expression):
            return parse_range_inequality(expression)
        else:
            return parse_range_closed(expression)

    if type(expression) == str:
        return parse_range(expression)

    elif type(expression) == list:
        parsed_data = [parse_range(range_) for range_ in expression]
        return parsed_data
    else:
        return parse_range(expression)

def calculate_min(values, frequencies):
    if all(isinstance(value,tuple) for value in values):
        filtered_data_ranges, filtered_frequencies = fill_missing_bins(values, frequencies)
        filtered_data_ranges, filtered_frequencies = merge_and_filter_intervals(filtered_data_ranges, filtered_frequencies)
        min_value = (filtered_data_ranges[0][0]+filtered_data_ranges[0][1])/2
    else:
        min_value = min(values)
    return min_value

def calculate_max(values, frequencies):
    if all(isinstance(value,tuple) for value in values):
        filtered_data_ranges, filtered_frequencies = fill_missing_bins(values, frequencies)
        filtered_data_ranges, filtered_frequencies = merge_and_filter_intervals(filtered_data_ranges, filtered_frequencies)
        max_value = (filtered_data_ranges[-1][0]+filtered_data_ranges[-1][1])/2
    else:
        max_value = max(values)
    return max_value

def generate_sample_data(values, frequencies):

    if all(isinstance(value,tuple) for value in values):
        all_values = []
        for (lower, upper), frequency in zip(values, frequencies):
            all_values.extend([(lower + upper) / 2] * int(frequency))

    elif all(isinstance(value,(int,float)) for value in values):
        all_values = []
        for value, frequency in zip(values, frequencies):
            all_values.extend([value]*int(frequency))

    else:

        return

    return all_values



def calculate_mean(values, frequencies):

    try:
        if all(isinstance(value,tuple) for value in values):

            # Calculate for grouped data
            total_weighted_value = sum((lower + upper) / 2 * frequency for (lower, upper), frequency in zip(values, frequencies))
            total_frequency = sum(frequencies)
            average_value = total_weighted_value / total_frequency

        elif all(isinstance(value,(int,float)) for value in values):

            # Calculate for ungrouped data
            total_weighted_value = sum(float(value)*float(frequency) for value, frequency in zip(values, frequencies))
            total_frequency = sum(frequencies)
            average_value = total_weighted_value / total_frequency

        else:
            return
    except ZeroDivisionError:
         return

    return average_value

def calculate_stdev(values, frequencies, variance=False, type='p'):

    mean = calculate_mean(values, frequencies)
    if mean is None:
        return None

    if all(isinstance(value, tuple) for value in values):
        # Calculate standard deviation for grouped data
        total_squared_deviation = sum(
            (((lower + upper) / 2 - mean) ** 2) * frequency for (lower, upper), frequency in zip(values, frequencies)
        )
        total_frequency = sum(frequencies)
    elif all(isinstance(value, (int, float)) for value in values):
        # Calculate standard deviation for ungrouped data
        total_squared_deviation = sum(
            ((value - mean) ** 2) * frequency for value, frequency in zip(values, frequencies)
        )
        total_frequency = sum(frequencies)
    else:
        return None

    if type=='s':
        variance_value = total_squared_deviation / (total_frequency-1)
    else:
        variance_value = total_squared_deviation / total_frequency

    standard_deviation = variance_value ** 0.5

    if variance:
        return standard_deviation, variance_value
    else:
        return standard_deviation

def calculate_median(values, frequencies):

    if all(isinstance(value,tuple) for value in values):
        median_value = calculate_percentile(values, frequencies, 50)
    else:
        all_values = generate_sample_data(values, frequencies)
        median_value = np.median(all_values)

    return median_value

def calculate_mode(values, frequencies):

    def find_max_key(dictionary):
        max_value = max(dictionary.values())
        max_keys = [key for key, value in dictionary.items() if value == max_value]
        return [max_keys[0]] if len(max_keys) == 1 else max_keys
    
    # Calculate mode
    all_values = generate_sample_data(values, frequencies)
    value_counts = {}
    for value in all_values:
        if value in value_counts:
            value_counts[value] += 1
        else:
            value_counts[value] = 1

    mode_value = find_max_key(value_counts)
    return mode_value

# Linear interpolation
def find_x_value_at_y(y_value, x_values, y_values):
    for i in range(1, len(y_values)):
        if y_value <= y_values[i]:
            x0, y0 = x_values[i - 1], y_values[i - 1]
            x1, y1 = x_values[i], y_values[i]
            # Linear interpolation
            x_value = x0 + (x1 - x0) * (y_value - y0) / (y1 - y0)
            return x_value
    return None


def calculate_decile(values, frequencies, k):

    data = generate_sample_data(values,frequencies)
    N = len(data)

    # Decile position
    pos = k * (N + 1) / 10.0
    # Integer part of the position
    f = int(np.floor(pos))
    # Fractional part of the position
    d = pos - f

    # If the position is exactly at an integer index
    if f == 0:
        return data[0]
    elif f >= N:
        return data[-1]
    else:
        return data[f - 1] + d * (data[f] - data[f - 1])

def sort_intervals(values, frequencies):
    # Zipping values and frequencies together
    zipped_pairs = list(zip(values, frequencies))

    # Sorting the zipped pairs based on the values list
    zipped_pairs.sort(key=lambda x: x[0])

    # Unzipping the sorted pairs back into two lists
    sorted_values, sorted_frequencies = zip(*zipped_pairs)

    # Converting them back to lists (optional)
    sorted_values = list(sorted_values)
    sorted_frequencies = list(sorted_frequencies)

    return sorted_values, sorted_frequencies


def find_percentile_ungrouped(values, frequencies, k):
    data = generate_sample_data(values, frequencies)
    """
    Find the k-th percentile for ungrouped data.

    :param data: List of numbers (ungrouped data)
    :param k: Percentile to find (0 < k <= 100)
    :return: k-th percentile value
    """
    # Sort the data
    sorted_data = sorted(data)
    n = len(sorted_data)

    # Calculate position
    position = (k / 100) * (n + 1)

    # If position is an integer, return the value at that position
    if position.is_integer():
        return sorted_data[int(position) - 1]

    # Otherwise, interpolate between the two closest values
    lower_idx = int(position) - 1
    upper_idx = lower_idx + 1

    if upper_idx < n:
        lower_value = sorted_data[lower_idx]
        upper_value = sorted_data[upper_idx]
        percentile_value = lower_value + (position - (lower_idx + 1)) * (upper_value - lower_value)
    else:
        percentile_value = sorted_data[lower_idx]

    return percentile_value


def find_percentile_grouped(intervals, data, k):

    if k<=0:
        return 0
    """
    Find the k-th percentile for grouped data using linear interpolation.

    :param data: List of frequencies corresponding to each class interval
    :param intervals: List of tuples representing class intervals (lower_bound, upper_bound)
    :param k: Percentile to find (0 < k <= 100)
    :return: k-th percentile value
    """
    # Convert intervals and frequencies into a DataFrame
    df = pd.DataFrame({'Interval': intervals, 'Frequency': data})

    # Calculate cumulative frequency
    df['Cumulative Frequency'] = df['Frequency'].cumsum()

    # Total number of frequencies
    n = df['Frequency'].sum()

    # Percentile position
    percentile_position = (k / 100) * n

    # Find the class interval that contains the k-th percentile
    for i in range(len(df)):
        if df.at[i, 'Cumulative Frequency'] >= percentile_position:
            # Get class interval details
            L = df.at[i, 'Interval'][0]  # Lower boundary of the class
            F = df.at[i - 1, 'Cumulative Frequency'] if i > 0 else 0  # Cumulative frequency before the class
            f = df.at[i, 'Frequency']  # Frequency of the class
            h = df.at[i, 'Interval'][1] - df.at[i, 'Interval'][0]  # Class width

            # Calculate the k-th percentile using interpolation formula
            P_k = L + ((percentile_position - F) / f) * h
            return P_k

def valid_data_ranges(intervals):
    """
    Validate a list of intervals to ensure there are no overlapping intervals.

    Parameters:
    - intervals: List of tuples or lists where each element is an interval (start, end).

    Returns:
    - bool: True if intervals are valid (no overlaps), False otherwise.
    """
    # Convert intervals to tuples if they are in list format
    intervals = [tuple(interval) for interval in intervals]

    # Sort intervals by start value, and by end value if start values are equal
    intervals.sort(key=lambda x: (x[0], x[1]))

    for i in range(1, len(intervals)):
        prev_start, prev_end = intervals[i - 1]
        curr_start, curr_end = intervals[i]

        # Check if the current interval starts before the previous interval ends
        if curr_start < prev_end:
            print(f"Invalid interval: {intervals[i]} overlaps with {intervals[i - 1]}")
            return False

    return True


def calculate_percentile(values, frequencies, k):
    if all(isinstance(value, tuple) for value in values):
        value = find_percentile_grouped(values, frequencies, k)
    else:
        value = find_percentile_ungrouped(values, frequencies, k)
    return value


def calculate_quartiles(values, frequencies):

    Q1 = calculate_percentile(values, frequencies, 25)
    Q2 = calculate_percentile(values, frequencies, 50)
    Q3 = calculate_percentile(values, frequencies, 75)

    return Q1, Q2, Q3



# Merge intervals together if there are intervals in between that have a frequency of 0 -> normally for plotting cumulative graphs
# Filter intervals by removing trailing intervals with a corresponding frequency of 0
def merge_and_filter_intervals(intervals, values):
    if all(isinstance(data_range,tuple) for data_range in intervals):
        data = list(zip(intervals,values))
        # Find the first tuple with a frequency higher than 0
        first_non_zero_index = next(i for i, (_, freq) in enumerate(data) if freq > 0)

        # Find the last tuple with a frequency higher than 0
        last_non_zero_index = len(data) - 1 - next(i for i, (_, freq) in enumerate(reversed(data)) if freq > 0)

        # Filter the list to include only the relevant range
        filtered_data = data[first_non_zero_index:last_non_zero_index + 1]

        # Merge zero frequency intervals
        merged_data = []
        for i in range(len(filtered_data)):
            if filtered_data[i][1] == 0 and merged_data:
                # Merge the current zero-frequency interval with the last interval in merged_data
                last_interval, last_freq = merged_data.pop()
                new_interval = (last_interval[0], filtered_data[i][0][1])
                merged_data.append((new_interval, last_freq))
            else:
                merged_data.append(filtered_data[i])

        revised_tuples, revised_frequencies = zip(*merged_data)

        return list(revised_tuples), list(revised_frequencies)
    else:
        return intervals, values


def generate_right_skewed_dist(size):
    # Parameters for the gamma distribution
    shape = 2.0  # Controls skewness
    scale = 2.0  # Stretches the distribution
    max_value = 500  # Maximum range value

    # Generate and scale the data
    data = np.random.gamma(shape, scale, size * 10)  # Generate more data for better distribution
    data = np.interp(data, (data.min(), data.max()), (0, max_value))  # Scale to 0-500
    data = np.round(data).astype(int)  # Round and convert to integers

    # Calculate histogram with `size` bins
    counts, _ = np.histogram(data, bins=size, range=(0, max_value))

    # Return the counts (bin heights) as the result
    counts = counts.tolist()
    return counts

def generate_left_skewed_dist(size):
    array = generate_right_skewed_dist(size)
    array.reverse()
    return array

def fill_missing_bins(bins, frequencies):

    if all(isinstance(data_range,tuple) for data_range in bins):
        updated_bins = []
        updated_frequencies = []

        for i in range(len(bins) - 1):
            current_bin = bins[i]
            next_bin = bins[i + 1]

            # Add current bin and its frequency to the updated lists
            updated_bins.append(current_bin)
            updated_frequencies.append(frequencies[i])

            # Check for gap between current bin and next bin
            if current_bin[1] != next_bin[0]:
                # Create the missing bin
                missing_bin = (current_bin[1], next_bin[0])
                # Insert the missing bin and its frequency (0)
                updated_bins.append(missing_bin)
                updated_frequencies.append(0)

        # Add the last bin and its frequency
        updated_bins.append(bins[-1])
        updated_frequencies.append(frequencies[-1])

        return updated_bins, updated_frequencies
    else:
        return bins, frequencies