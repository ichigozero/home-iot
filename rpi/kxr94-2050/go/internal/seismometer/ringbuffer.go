package seismometer

import "sort"

type ringBuffer struct {
	values []float32
	size   int
	index  int
}

func newRingBuffer(size int) *ringBuffer {
	return &ringBuffer{
		values: make([]float32, size),
		size:   size,
	}
}

func (r *ringBuffer) push(value float32) {
	r.values[r.index] = value
	r.index = (r.index + 1) % r.size
}

func (r *ringBuffer) getSum() float32 {
	var sum float32 = 0

	for i := 0; i < r.size; i++ {
		sum += r.values[i]
	}

	return sum
}

func (r *ringBuffer) getSortedValues() []float32 {
	sortedValues := make([]float32, r.size)
	copy(sortedValues, r.values)

	sort.Slice(sortedValues, func(i, j int) bool {
		return sortedValues[i] > sortedValues[j]
	})

	return sortedValues
}
