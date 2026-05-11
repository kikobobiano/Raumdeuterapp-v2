/** Minimal typings — `d3-contour` ships JS only. */

declare module "d3-contour" {
  interface ContourFeature {
    type: string;
    value: number;
    coordinates: number[][][][];
  }

  interface ContourGenerator {
    (values: ArrayLike<number>): ContourFeature[];
    size(dimensions: [number, number]): ContourGenerator;
    thresholds(values: number[] | ((_values: Float32Array) => number[])): ContourGenerator;
    smooth(enabled: boolean): ContourGenerator;
  }

  export function contours(): ContourGenerator;
}
