(*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *)

type t [@@deriving show, eq, compare, hash]

val create : PyrePath.t -> t

val raw : t -> PyrePath.t

val original_source_path : t -> SourcePath.t